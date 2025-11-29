import logging
from apps.users.models import UserProfile
from apps.users.services import UTFPRAuthService
from apps.courses.models import Course, SearchTerm
from infra.jobspy.service import JobSearchService
from infra.waha.client import WahaClient
from apps.bot.models import BotConfiguration, InteractionLog, BotMessage

logger = logging.getLogger(__name__)

class BotService:
    """
    Controla o fluxo de conversação do bot.
    """

    BRAND_HEADER = (
        "🌟 *CapyVagas* | Assistente de Vagas da UTFPR\n"
        "Conecto você às oportunidades certas para o seu curso."
    )
    
    def __init__(
        self,
        auth_service: UTFPRAuthService | None = None,
        job_service: JobSearchService | None = None,
        waha_client: WahaClient | None = None,
    ):
        waha_settings = BotConfiguration.get_active()
        self.auth_service = auth_service or UTFPRAuthService()
        self.job_service = job_service or JobSearchService()
        self.waha_client = waha_client or WahaClient(settings=waha_settings)

    def get_text(self, key: str, default: str) -> str:
        """Busca mensagem configurada ou usa default."""
        try:
            msg = BotMessage.objects.filter(key=key).first()
            if msg and msg.text.strip():
                return msg.text
        except Exception:
            pass
        return default

    def process_message(self, chat_id, message, from_me):
        """
        Processa uma mensagem recebida.
        """
        if from_me:
            return

        if not message or not message.strip():
            return

        text = message.strip().lower()
        
        # Identificar usuário
        try:
            user = UserProfile.objects.get(phone_number=chat_id)
        except UserProfile.DoesNotExist:
            user = UserProfile.objects.create(phone_number=chat_id)

        InteractionLog.objects.create(
            user=user,
            message_content=message,
            message_type="RECEIVED",
            session_id=self.waha_client.settings.session_name,
        )

        # --- COMANDOS GLOBAIS (Prioridade Máxima) ---
        if text in {"menu", "inicio", "início", "start", "começar"}:
            self.reset_state(user)
            self.send_menu(user, chat_id)
            return

        if text in {"cancelar", "voltar", "sair"}:
            # Se estiver logado e digitar sair, faz logout
            if text == "sair" and user.is_authenticated_utfpr:
                 self.handle_logout(user, chat_id)
                 return
            
            self.reset_state(user)
            self.waha_client.send_message(chat_id, "✅ Ação cancelada.")
            self.send_menu(user, chat_id)
            return

        # --- MÁQUINA DE ESTADOS ---
        if user.current_action:
            if self.handle_pending_action(user, chat_id, text):
                return
            else:
                # Se a ação falhou ou não era esperada, mas o estado persiste
                pass

        # --- COMANDOS DO MENU PRINCIPAL ---
        if text in {"1", "cadastrar", "login", "entrar"}:
            self.start_login_flow_step1(user, chat_id)
            return

        if text in {"2", "logout", "deslogar"}:
            self.handle_logout(user, chat_id)
            return

        if text in {"3", "vagas", "buscar", "cursos"}:
            self.start_course_selection(user, chat_id)
            return

        # Comando não reconhecido
        self.send_unknown_command(user, chat_id)

    def reset_state(self, user: UserProfile):
        """Limpa o estado conversacional do usuário."""
        user.current_action = None
        user.flow_data = {}
        user.save(update_fields=["current_action", "flow_data", "last_activity"])


    # --- FLUXO DE LOGIN ---

    def start_login_flow_step1(self, user: UserProfile, chat_id: str):
        """Passo 1: Pedir RA"""
        if user.is_authenticated_utfpr:
             self.waha_client.send_message(chat_id, "✅ Você já está cadastrado! Selecione a opção 3 para buscar vagas.")
             return

        user.current_action = "login_step_ra"
        user.flow_data = {} # Limpa dados anteriores
        user.save(update_fields=["current_action", "flow_data", "last_activity"])
        
        msg = self.get_text(
            'login_prompt_ra', 
            "🔐 *Cadastro UTFPR*\n\nPor favor, digite seu **RA** (ex: a1234567):\n\n_(Digite 'cancelar' para voltar)_"
        )
        self.send_msg(user, chat_id, msg)

    def handle_login_ra(self, user: UserProfile, chat_id: str, text: str):
        ra = text.strip().lower()
        
        # Validação básica de RA (pode ser ajustada)
        if len(ra) < 5: # muito curto
             self.send_msg(user, chat_id, "❌ RA muito curto. Tente novamente ou digite 'cancelar'.")
             return

        # Salva RA e avança
        user.flow_data['temp_ra'] = ra
        user.current_action = "login_step_password"
        user.save(update_fields=["current_action", "flow_data", "last_activity"])

        msg = self.get_text(
            'login_prompt_password',
            "🔑 Agora digite sua **Senha** do Portal do Aluno:\n\n_(Seus dados são usados apenas para validação e busca de vagas)_"
        )
        self.send_msg(user, chat_id, msg)

    def handle_login_password(self, user: UserProfile, chat_id: str, text: str):
        password = text.strip()
        ra = user.flow_data.get('temp_ra')

        if not ra:
            self.send_msg(user, chat_id, "❌ Erro de fluxo. Por favor, comece novamente.")
            self.reset_state(user)
            return

        self.send_msg(user, chat_id, "🔄 Validando credenciais...")

        if self.auth_service.authenticate(ra, password):
            self.auth_service.link_user(chat_id, ra, password)
            self.reset_state(user) # Limpa estado após sucesso
            
            msg = self.get_text(
                'login_success',
                "✅ **Cadastro Confirmado!**\n\nAgora você pode buscar vagas personalizadas para seu curso.\n\nEscolha a opção 3 no menu."
            )
            self.send_msg(user, chat_id, msg)
            self.send_menu(user, chat_id)
        else:
            # Falha: permite tentar senha de novo ou cancelar
            msg = self.get_text(
                'login_error',
                "❌ **Falha no login.**\nRA ou senha incorretos.\n\nTente digitar a senha novamente ou digite 'cancelar' para sair."
            )
            self.send_msg(user, chat_id, msg)
            # Mantém no estado de senha

    def handle_logout(self, user, chat_id):
        self.auth_service.logout(chat_id)
        self.waha_client.send_message(chat_id, "🔒 Você saiu do sistema. Até logo!")
        self._log_sent(user, "🔒 Você saiu do sistema. Até logo!")
        user.current_action = None
        user.selected_course = None
        user.selected_term = None
        user.save(update_fields=["current_action", "selected_course", "selected_term", "last_activity"])

    # --- FLUXO DE CURSO ---

    def start_course_selection(self, user: UserProfile, chat_id: str):
        if not user.is_authenticated_utfpr:
            self.send_msg(user, chat_id, "🔒 Você precisa se cadastrar primeiro (Opção 1).")
            return

        courses = list(Course.objects.filter(is_active=True).order_by("order", "name"))
        if not courses:
            self.send_msg(user, chat_id, "⚠️ Nenhum curso cadastrado no sistema.")
            return

        menu_lines = [f"*{idx+1}*) {course.name}" for idx, course in enumerate(courses)]
        msg = (
            "🎓 **Selecione seu Curso**:\n\n" + 
            "\n".join(menu_lines) + 
            "\n\nDigite o número correspondente:"
        )
        
        user.current_action = "course_selection"
        user.save(update_fields=["current_action", "last_activity"])
        self.send_msg(user, chat_id, msg)

    def handle_course_selection(self, user: UserProfile, chat_id: str, text: str):
        courses = list(Course.objects.filter(is_active=True).order_by("order", "name"))
        
        try:
            idx = int(text) - 1
            if 0 <= idx < len(courses):
                course = courses[idx]
                user.selected_course = course
                user.save(update_fields=["selected_course"])
                self.start_term_selection(user, chat_id)
            else:
                self.send_msg(user, chat_id, "❌ Número inválido. Tente novamente.")
        except ValueError:
            self.send_msg(user, chat_id, "❌ Digite apenas o número do curso.")

    def start_term_selection(self, user: UserProfile, chat_id: str):
        terms = list(user.selected_course.search_terms.filter(is_default=True).order_by("-priority"))
        
        if not terms:
            self.send_msg(user, chat_id, f"⚠️ O curso {user.selected_course.name} não tem termos de busca configurados.")
            self.reset_state(user)
            return

        menu_lines = [f"*{idx+1}*) {term.term}" for idx, term in enumerate(terms)]
        menu_lines.append(f"*{len(terms)+1}*) Buscar Todos")

        msg = (
            f"🔍 Curso: *{user.selected_course.name}*\n"
            "Escolha o termo de busca:\n\n" + 
            "\n".join(menu_lines) + 
            "\n\nDigite o número:"
        )

        user.current_action = "term_selection"
        user.save(update_fields=["current_action", "last_activity"])
        self.send_msg(user, chat_id, msg)

    def handle_term_selection(self, user: UserProfile, chat_id: str, text: str):
        terms = list(user.selected_course.search_terms.filter(is_default=True).order_by("-priority"))
        
        try:
            idx = int(text) - 1
            selected_terms_list = []
            
            if idx == len(terms): # Buscar Todos
                selected_terms_list = [t.term for t in terms]
                term_name = "Todos os termos"
            elif 0 <= idx < len(terms):
                term = terms[idx]
                user.selected_term = term
                user.save(update_fields=["selected_term"])
                selected_terms_list = [term.term]
                term_name = term.term
            else:
                self.send_msg(user, chat_id, "❌ Número inválido.")
                return

            self.reset_state(user)
            self.perform_search(user, chat_id, selected_terms_list, term_name)

        except ValueError:
            self.send_msg(user, chat_id, "❌ Digite apenas o número.")

    def perform_search(self, user: UserProfile, chat_id: str, terms: list, term_name: str):
        self.send_msg(user, chat_id, f"🔎 Buscando vagas para: *{term_name}*... Aguarde.")
        
        try:
            jobs = self.job_service.search(terms, limit=5)
        except Exception as e:
            logger.error(f"Erro na busca de vagas: {e}")
            jobs = []
        
        if not jobs:
            self.send_msg(user, chat_id, "😔 Nenhuma vaga encontrada no momento para esses termos.")
            self.send_menu(user, chat_id)
            return

        msg_lines = [f"🚀 *Vagas Encontradas ({len(jobs)})*:"]
        for job in jobs:
            msg_lines.append(
                f"\n💼 *{job.get('title', 'Vaga')}*\n"
                f"🏢 {job.get('company', 'Empresa')}\n"
                f"🔗 {job.get('url', '#')}"
            )
        
        self.send_msg(user, chat_id, "\n".join(msg_lines))
        # Não reenviar menu imediatamente para não poluir, ou reenviar?
        # Melhor deixar o usuário ler e se quiser manda 'menu'.

    # --- UTILITÁRIOS ---

    def handle_pending_action(self, user: UserProfile, chat_id: str, text: str) -> bool:
        if user.current_action == "login_step_ra":
            self.handle_login_ra(user, chat_id, text)
            return True
        
        if user.current_action == "login_step_password":
            self.handle_login_password(user, chat_id, text)
            return True

        if user.current_action == "course_selection":
            self.handle_course_selection(user, chat_id, text)
            return True

        if user.current_action == "term_selection":
            self.handle_term_selection(user, chat_id, text)
            return True

        return False

    def send_menu(self, user: UserProfile, chat_id: str):
        menu_default = (
            f"{self.BRAND_HEADER}\n\n"
            "Escolha uma opção:\n\n"
            "1️⃣  *Cadastrar/Login* (Aluno)\n"
            "2️⃣  *Sair/Logout*\n"
            "3️⃣  *Buscar Vagas*\n\n"
            "📝 Digite o número da opção."
        )
        msg = self.get_text('welcome', menu_default)
        
        status = "✅ Logado" if user.is_authenticated_utfpr else "❌ Não logado"
        msg += f"\n\n_Status: {status}_"

        self.send_msg(user, chat_id, msg)

    def send_unknown_command(self, user: UserProfile, chat_id: str):
        msg = self.get_text('unknown_command', "🤔 Não entendi. Digite *menu* para ver as opções.")
        self.send_msg(user, chat_id, msg)

    def send_msg(self, user: UserProfile, chat_id: str, text: str):
        """Envia mensagem via WAHA e loga."""
        self.waha_client.send_message(chat_id, text)
        InteractionLog.objects.create(
            user=user,
            message_content=text,
            message_type="SENT",
            session_id=self.waha_client.settings.session_name,
        )
