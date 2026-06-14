from django.test import TestCase

from apps.bot.state_machine import (
    CANONICAL_STATES,
    ROUTE_AUTH,
    ROUTE_COMPANY,
    ROUTE_IDLE,
    ROUTE_JOB_SEARCH,
    STATE_COMPANY_ONBOARDING_SELECTION,
    STATE_COURSE_SELECTION,
    STATE_IDLE,
    STATE_LOGIN_STEP_EMAIL,
    STATE_LOGIN_STEP_PASSWORD,
    STATE_LOGIN_STEP_RA,
    STATE_LOGIN_STEP_WAITING_CONFIRMATION,
    STATE_TERM_SELECTION,
    ConversationFlowStateMachine,
    has_active_flow,
    is_waiting_confirmation,
    normalize_current_action,
    normalized_flow_state,
    route_for_action,
)


class ConversationStateMachineContractTests(TestCase):
    def test_canonical_states_cover_expected_flows(self):
        from apps.bot.state_machine import (
            STATE_COMPANY_LOGIN_EMAIL,
            STATE_COMPANY_LOGIN_PASSWORD,
            STATE_CONFIRM_APPLICATION,
            STATE_LOCAL_JOB_DETAIL,
            STATE_LOCAL_JOBS_LIST,
            STATE_PROFILE_LINK,
            STATE_PROFILE_PERIODO,
            STATE_PROFILE_SKILLS,
        )

        expected = {
            STATE_LOGIN_STEP_RA,
            STATE_LOGIN_STEP_PASSWORD,
            STATE_LOGIN_STEP_EMAIL,
            STATE_LOGIN_STEP_WAITING_CONFIRMATION,
            STATE_COURSE_SELECTION,
            STATE_TERM_SELECTION,
            STATE_COMPANY_ONBOARDING_SELECTION,
            STATE_COMPANY_LOGIN_EMAIL,
            STATE_COMPANY_LOGIN_PASSWORD,
            STATE_LOCAL_JOBS_LIST,
            STATE_LOCAL_JOB_DETAIL,
            STATE_PROFILE_PERIODO,
            STATE_PROFILE_SKILLS,
            STATE_PROFILE_LINK,
            STATE_CONFIRM_APPLICATION,
        }
        self.assertSetEqual(CANONICAL_STATES, expected)

    def test_normalize_current_action_falls_back_to_idle(self):
        self.assertEqual(normalize_current_action(None), STATE_IDLE)
        self.assertEqual(normalize_current_action(""), STATE_IDLE)
        self.assertEqual(normalize_current_action("menu"), STATE_IDLE)
        self.assertEqual(normalize_current_action("unknown_state"), STATE_IDLE)

    def test_normalized_flow_state_keeps_db_idle_as_none(self):
        idle_state = normalized_flow_state(None)
        self.assertEqual(idle_state.runtime, STATE_IDLE)
        self.assertIsNone(idle_state.persisted)

        active_state = normalized_flow_state(STATE_LOGIN_STEP_PASSWORD)
        self.assertEqual(active_state.runtime, STATE_LOGIN_STEP_PASSWORD)
        self.assertEqual(active_state.persisted, STATE_LOGIN_STEP_PASSWORD)

    def test_route_resolution_for_all_state_groups(self):
        self.assertEqual(route_for_action(STATE_LOGIN_STEP_RA), ROUTE_AUTH)
        self.assertEqual(route_for_action(STATE_LOGIN_STEP_WAITING_CONFIRMATION), ROUTE_AUTH)
        self.assertEqual(route_for_action(STATE_COURSE_SELECTION), ROUTE_JOB_SEARCH)
        self.assertEqual(route_for_action(STATE_TERM_SELECTION), ROUTE_JOB_SEARCH)
        self.assertEqual(route_for_action(STATE_COMPANY_ONBOARDING_SELECTION), ROUTE_COMPANY)
        self.assertEqual(route_for_action(None), ROUTE_IDLE)

    def test_waiting_confirmation_and_active_flow_helpers(self):
        self.assertTrue(is_waiting_confirmation(STATE_LOGIN_STEP_WAITING_CONFIRMATION))
        self.assertFalse(is_waiting_confirmation(STATE_LOGIN_STEP_RA))
        self.assertTrue(has_active_flow(STATE_COURSE_SELECTION))
        self.assertFalse(has_active_flow(None))

    def test_statemachine_can_start_from_normalized_state(self):
        machine = ConversationFlowStateMachine(start_value=normalize_current_action("waiting_ra"))
        self.assertEqual(machine.current_state.id, STATE_LOGIN_STEP_RA)
