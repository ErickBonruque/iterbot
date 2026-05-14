"""Central registry for bot message templates."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MessageTemplate:
    key: str
    text: str


@dataclass(frozen=True)
class AuthMessages:
    login_already_registered: MessageTemplate = MessageTemplate(
        "auth.login_already_registered",
        "✅ Você já está cadastrado! Selecione a opção 1 para buscar vagas.",
    )
    login_prompt_ra: MessageTemplate = MessageTemplate(
        "auth.login_prompt_ra",
        "🔐 *Cadastro UTFPR*\n\nPor favor, digite seu **RA** (ex: a1234567):\n\n_(Digite 'cancelar' para voltar)_",
    )
    login_ra_too_short: MessageTemplate = MessageTemplate(
        "auth.login_ra_too_short",
        "❌ RA muito curto. Tente novamente ou digite 'cancelar'.",
    )
    login_prompt_password: MessageTemplate = MessageTemplate(
        "auth.login_prompt_password",
        "🔑 Agora digite sua **Senha** do Portal do Aluno:\n\n_(Seus dados são criptografados e usados apenas para validação)_",
    )
    login_validating_credentials: MessageTemplate = MessageTemplate(
        "auth.login_validating_credentials",
        "🔄 Validando credenciais...",
    )
    login_prompt_email: MessageTemplate = MessageTemplate(
        "auth.login_prompt_email",
        "🔐 *Verificação de E-mail*\n\nPor favor, digite seu **e-mail institucional** (@alunos.utfpr.edu.br):\n\n_(Digite 'cancelar' para voltar)_",
    )
    login_error: MessageTemplate = MessageTemplate(
        "auth.login_error",
        "❌ **Falha no login.**\nRA ou senha incorretos.\n\nTente digitar a senha novamente ou digite 'cancelar' para sair.",
    )
    login_flow_error: MessageTemplate = MessageTemplate(
        "auth.login_flow_error",
        "❌ Erro de fluxo. Por favor, comece novamente.",
    )
    login_email_too_short: MessageTemplate = MessageTemplate(
        "auth.login_email_too_short",
        "❌ E-mail muito curto. Digite seu e-mail completo (@alunos.utfpr.edu.br).",
    )
    login_email_invalid: MessageTemplate = MessageTemplate(
        "auth.login_email_invalid",
        "❌ E-mail inválido. Use apenas endereços @alunos.utfpr.edu.br.\n\nDigite 'cancelar' para voltar ao menu.",
    )
    login_waiting_confirmation: MessageTemplate = MessageTemplate(
        "auth.login_waiting_confirmation",
        "📧 *Confirmação de E-mail*\n\nEnviamos um link de confirmação para:\n`{email}`\n\nClique no link para confirmar seu e-mail.\nO link expira em 24 horas.\n\nApós confirmar, você terá acesso ao bot.\n\nDigite 'reenviar' se não recebeu o email.",
    )
    login_resend_success: MessageTemplate = MessageTemplate(
        "auth.login_resend_success",
        "📧 E-mail de confirmação reenviado!\n\nVerifique sua caixa de entrada (e spam também).\n\nDigite 'menu' para voltar ao início.",
    )
    login_resend_error: MessageTemplate = MessageTemplate(
        "auth.login_resend_error",
        "❌ Erro ao reenviar. Tente novamente ou digite 'menu' para voltar.",
    )
    login_waiting_status: MessageTemplate = MessageTemplate(
        "auth.login_waiting_status",
        "⏳ Aguardando confirmação de e-mail...\n\nClique no link enviado para seu email ou digite 'reenviar' para receber novamente.\n\nDigite 'menu' para voltar ao início.",
    )
    logout_success: MessageTemplate = MessageTemplate(
        "auth.logout_success",
        "🔒 Você saiu do sistema. Até logo!",
    )
    login_welcome_back: MessageTemplate = MessageTemplate(
        "auth.login_welcome_back",
        "✅ *Bem-vindo de volta!*\n\nSeu e-mail `{email}` já foi verificado anteriormente, então você está autenticado direto.\n\nDigite *menu* para ver as opções disponíveis.",
    )


@dataclass(frozen=True)
class MenuMessages:
    brand_header: str = (
        "🌟 *IterBot* | Assistente de Vagas da UTFPR\n"
        "Conecto você às oportunidades certas para o seu curso."
    )
    main_authenticated: MessageTemplate = MessageTemplate(
        "menu.main_authenticated",
        "{brand_header}\n\n👤 *Usuário*: {ra}\n\n📋 *Menu Principal*:\n1️⃣ Buscar Vagas\n2️⃣ Ver Review de Vagas\n3️⃣ Sair da Conta\n4️⃣ Trocar Curso Preferido\n\nDigite o número da opção desejada.",
    )
    main_unauthenticated: MessageTemplate = MessageTemplate(
        "menu.main_unauthenticated",
        "{brand_header}\n\n📋 *Menu Principal*:\n1️⃣ Fazer Cadastro/Login\n2️⃣ Sou empresa (cadastrar vaga)\n3️⃣ Buscar Vagas\n\nDigite o número da opção desejada.",
    )
    company_onboarding_menu: MessageTemplate = MessageTemplate(
        "menu.company_onboarding_menu",
        "{brand_header}\n\n🏢 *Onboarding para Empresas*\n\n1️⃣ Cadastrar empresa\n2️⃣ Ja tenho conta / publicar vaga\n\nDigite 1 ou 2 para continuar.",
    )
    company_onboarding_signup: MessageTemplate = MessageTemplate(
        "menu.company_onboarding_signup",
        "✅ *Cadastro de Empresa*\n\n1) Crie sua conta: {signup_url}\n2) Confirme os dados da empresa\n3) Entre no portal para publicar sua primeira vaga",
    )
    company_onboarding_publish: MessageTemplate = MessageTemplate(
        "menu.company_onboarding_publish",
        "✅ *Publicar Vaga*\n\nAcesse sua conta: {login_url}\nNova vaga: {new_job_url}",
    )
    unknown_command: MessageTemplate = MessageTemplate(
        "menu.unknown_command",
        "❓ Comando não reconhecido.\n\nDigite *menu* para ver as opções disponíveis.",
    )


@dataclass(frozen=True)
class SearchMessages:
    auth_required: MessageTemplate = MessageTemplate(
        "search.auth_required",
        "🔒 Você precisa se cadastrar primeiro (Opção 1).",
    )
    no_courses: MessageTemplate = MessageTemplate(
        "search.no_courses",
        "⚠️ Nenhum curso cadastrado no sistema.",
    )
    selection_intro: MessageTemplate = MessageTemplate(
        "search.selection_intro",
        "🎓 *Selecione seu Curso*:\n\n{courses_menu}\n\nDigite o número correspondente:",
    )
    invalid_course_non_numeric: MessageTemplate = MessageTemplate(
        "search.invalid_course_non_numeric",
        "❌ Digite apenas o número do curso.",
    )
    invalid_course_number: MessageTemplate = MessageTemplate(
        "search.invalid_course_number",
        "❌ Número inválido. Tente novamente.",
    )
    missing_course: MessageTemplate = MessageTemplate(
        "search.missing_course",
        "❌ Curso não selecionado. Comece novamente pelo menu.",
    )
    no_terms_for_course: MessageTemplate = MessageTemplate(
        "search.no_terms_for_course",
        "⚠️ O curso {course_name} não tem termos de busca configurados.",
    )
    term_selection_intro: MessageTemplate = MessageTemplate(
        "search.term_selection_intro",
        "🔍 Curso: *{course_name}*\nEscolha o termo de busca:\n\n{terms_menu}\n\nDigite o número:",
    )
    invalid_term_non_numeric: MessageTemplate = MessageTemplate(
        "search.invalid_term_non_numeric",
        "❌ Digite apenas o número.",
    )
    invalid_term_number: MessageTemplate = MessageTemplate(
        "search.invalid_term_number",
        "❌ Número inválido.",
    )
    searching_jobs: MessageTemplate = MessageTemplate(
        "search.searching_jobs",
        "🔎 Buscando vagas para: *{term_name}*... Aguarde.",
    )
    search_timeout: MessageTemplate = MessageTemplate(
        "search.search_timeout",
        "⏰ A busca demorou demais e foi cancelada. Tente novamente mais tarde.\n\nDigite *menu* para voltar ao menu principal.",
    )
    search_error: MessageTemplate = MessageTemplate(
        "search.search_error",
        "⚠️ Ocorreu um erro ao buscar vagas. Tente novamente mais tarde.\n\nDigite *menu* para voltar ao menu principal.",
    )
    no_jobs: MessageTemplate = MessageTemplate(
        "search.no_jobs",
        "😔 Nenhuma vaga encontrada no momento para esses termos.",
    )
    results_header: MessageTemplate = MessageTemplate(
        "search.results_header",
        "🚀 *Vagas para {course_name}* (termo: *{term_name}*)",
    )
    course_preference_saved: MessageTemplate = MessageTemplate(
        "search.course_preference_saved",
        "✅ Curso *{course_name}* salvo como preferência. Na próxima busca vou pular esta etapa.",
    )
    course_preference_updated: MessageTemplate = MessageTemplate(
        "search.course_preference_updated",
        "✅ Preferência atualizada para *{course_name}*.",
    )


@dataclass(frozen=True)
class ReviewMessages:
    missing_course: MessageTemplate = MessageTemplate(
        "review.missing_course",
        "⚠️ Você não tem curso definido.\n\nUse a opção *1 - Buscar Vagas* para selecionar seu curso primeiro.",
    )
    searching_review: MessageTemplate = MessageTemplate(
        "review.searching_review",
        "🔎 Buscando vagas para você... Aguarde um momento.",
    )
    review_error: MessageTemplate = MessageTemplate(
        "review.review_error",
        "❌ Ocorreu um erro ao buscar vagas. Tente novamente mais tarde.",
    )
    no_jobs: MessageTemplate = MessageTemplate(
        "review.no_jobs",
        "😔 Não encontrei vagas para o seu curso no momento.\n\n_Tente novamente em alguns dias ou use a opção *1 - Buscar Vagas* para busca manual._",
    )
    weekly_header: MessageTemplate = MessageTemplate(
        "review.weekly_header",
        "🎓 *Review de Vagas — {course_name}*",
    )
    weekly_summary: MessageTemplate = MessageTemplate(
        "review.weekly_summary",
        "Encontrei *{count}* oportunidades para voce esta semana:",
    )
    weekly_footer: MessageTemplate = MessageTemplate(
        "review.weekly_footer",
        '_Para ver mais vagas, acesse o menu e escolha "Buscar Vagas"._',
    )


@dataclass(frozen=True)
class SystemMessages:
    action_cancelled: MessageTemplate = MessageTemplate(
        "system.action_cancelled",
        "✅ Ação cancelada.",
    )
    portal_unavailable: MessageTemplate = MessageTemplate(
        "system.portal_unavailable",
        "⚠️ Portal de empresas temporariamente indisponivel. Tente novamente em alguns minutos.",
    )
    webhook_error: MessageTemplate = MessageTemplate(
        "system.webhook_error",
        "Erro",
    )
    method_not_allowed: MessageTemplate = MessageTemplate(
        "system.method_not_allowed",
        "Método não permitido",
    )


@dataclass(frozen=True)
class TaskMessages:
    alert_subject_offline: MessageTemplate = MessageTemplate(
        "tasks.alert_subject_offline",
        "[IterBot] ⚠️ Bot WhatsApp offline",
    )
    alert_offline_intro: MessageTemplate = MessageTemplate(
        "tasks.alert_offline_intro",
        "O bot WhatsApp (sessão: {session_name}) foi detectado como OFFLINE.",
    )
    alert_status_line: MessageTemplate = MessageTemplate(
        "tasks.alert_status_line",
        "Status atual: {current_status}",
    )
    alert_error_line: MessageTemplate = MessageTemplate(
        "tasks.alert_error_line",
        "Mensagem de erro: {error_message}",
    )
    alert_reconnect_line: MessageTemplate = MessageTemplate(
        "tasks.alert_reconnect_line",
        "Tentativa de reconexão automática: {reconnect_result}",
    )
    confirm_email_subject: MessageTemplate = MessageTemplate(
        "tasks.confirm_email_subject",
        "[IterBot] Confirme seu e-mail institucional",
    )
    confirm_email_greeting: MessageTemplate = MessageTemplate(
        "tasks.confirm_email_greeting",
        "Olá, {ra}!",
    )


@dataclass(frozen=True)
class BotMessages:
    auth: AuthMessages = AuthMessages()
    menu: MenuMessages = MenuMessages()
    search: SearchMessages = SearchMessages()
    review: ReviewMessages = ReviewMessages()
    system: SystemMessages = SystemMessages()
    tasks: TaskMessages = TaskMessages()


BOT_MESSAGES = BotMessages()
