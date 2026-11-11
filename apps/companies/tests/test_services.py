from django.test import SimpleTestCase

from apps.companies.services import CompaniesService
from apps.jobs.models import Job, JobStatus


class TestPrepareJobForUpdate(SimpleTestCase):
    """Regra de reenvio: editar vaga aprovada ou recusada devolve para análise."""

    def _vaga(self, status, motivo=None):
        return Job(titulo="Vaga", status=status, rejection_reason=motivo)

    def test_aprovada_alterada_volta_para_pending(self):
        vaga = self._vaga(JobStatus.APPROVED)

        reenviada = CompaniesService.prepare_job_for_update(vaga, changed=True)

        self.assertTrue(reenviada)
        self.assertEqual(vaga.status, JobStatus.PENDING)

    def test_recusada_alterada_volta_para_pending_e_limpa_o_motivo(self):
        vaga = self._vaga(JobStatus.REJECTED, "Fora do escopo")

        reenviada = CompaniesService.prepare_job_for_update(vaga, changed=True)

        self.assertTrue(reenviada)
        self.assertEqual(vaga.status, JobStatus.PENDING)
        self.assertIsNone(vaga.rejection_reason)

    def test_sem_alteracao_nao_mexe_em_nada(self):
        for status in (JobStatus.APPROVED, JobStatus.REJECTED):
            with self.subTest(status=status):
                vaga = self._vaga(status, "Motivo")

                reenviada = CompaniesService.prepare_job_for_update(vaga, changed=False)

                self.assertFalse(reenviada)
                self.assertEqual(vaga.status, status)
                self.assertEqual(vaga.rejection_reason, "Motivo")

    def test_outros_status_nao_sao_reenviados(self):
        for status in (JobStatus.PENDING, JobStatus.DRAFT, JobStatus.EXPIRED, JobStatus.REMOVED):
            with self.subTest(status=status):
                vaga = self._vaga(status)

                reenviada = CompaniesService.prepare_job_for_update(vaga, changed=True)

                self.assertFalse(reenviada)
                self.assertEqual(vaga.status, status)
