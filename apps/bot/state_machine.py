"""Conversation flow state machine and normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass

from statemachine import State, StateMachine

STATE_IDLE = "idle"
STATE_LOGIN_STEP_RA = "login_step_ra"
STATE_LOGIN_STEP_PASSWORD = "login_step_password"
STATE_LOGIN_STEP_EMAIL = "login_step_email"
STATE_LOGIN_STEP_WAITING_CONFIRMATION = "login_step_waiting_confirmation"
STATE_COURSE_SELECTION = "course_selection"
STATE_TERM_SELECTION = "term_selection"
STATE_COMPANY_ONBOARDING_SELECTION = "company_onboarding_selection"
STATE_COMPANY_LOGIN_EMAIL = "company_login_email"
STATE_COMPANY_LOGIN_PASSWORD = "company_login_password"
STATE_COMPANY_WAITING_CONFIRMATION = "company_waiting_confirmation"  # legacy
STATE_LOCAL_JOBS_LIST = "local_jobs_list"
STATE_LOCAL_JOB_DETAIL = "local_job_detail"
STATE_PROFILE_PERIODO = "profile_periodo"
STATE_PROFILE_SKILLS = "profile_skills"
STATE_PROFILE_LINK = "profile_link"
STATE_CONFIRM_APPLICATION = "confirm_application"

CANONICAL_STATES = {
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

LEGACY_STATE_ALIASES = {
    "waiting_ra": STATE_LOGIN_STEP_RA,
    "waiting_password": STATE_LOGIN_STEP_PASSWORD,
    "waiting_email": STATE_LOGIN_STEP_EMAIL,
    "waiting_confirmation": STATE_LOGIN_STEP_WAITING_CONFIRMATION,
    "menu": STATE_IDLE,
    "start": STATE_IDLE,
}

ROUTE_IDLE = "idle"
ROUTE_AUTH = "auth"
ROUTE_JOB_SEARCH = "job_search"
ROUTE_COMPANY = "company_onboarding"
ROUTE_LOCAL_JOBS = "local_jobs"
ROUTE_APPLICATION = "application"

AUTH_ROUTE_STATES = {
    STATE_LOGIN_STEP_RA,
    STATE_LOGIN_STEP_PASSWORD,
    STATE_LOGIN_STEP_EMAIL,
    STATE_LOGIN_STEP_WAITING_CONFIRMATION,
}
JOB_ROUTE_STATES = {
    STATE_COURSE_SELECTION,
    STATE_TERM_SELECTION,
}
COMPANY_ROUTE_STATES = {
    STATE_COMPANY_ONBOARDING_SELECTION,
    STATE_COMPANY_LOGIN_EMAIL,
    STATE_COMPANY_LOGIN_PASSWORD,
}
LOCAL_JOBS_ROUTE_STATES = {
    STATE_LOCAL_JOBS_LIST,
    STATE_LOCAL_JOB_DETAIL,
}
APPLICATION_ROUTE_STATES = {
    STATE_PROFILE_PERIODO,
    STATE_PROFILE_SKILLS,
    STATE_PROFILE_LINK,
    STATE_CONFIRM_APPLICATION,
}


class ConversationFlowStateMachine(StateMachine):
    """Defines valid conversation states and explicit transitions."""

    idle = State(STATE_IDLE, initial=True)
    login_step_ra = State(STATE_LOGIN_STEP_RA)
    login_step_password = State(STATE_LOGIN_STEP_PASSWORD)
    login_step_email = State(STATE_LOGIN_STEP_EMAIL)
    login_step_waiting_confirmation = State(STATE_LOGIN_STEP_WAITING_CONFIRMATION)
    course_selection = State(STATE_COURSE_SELECTION)
    term_selection = State(STATE_TERM_SELECTION)
    company_onboarding_selection = State(STATE_COMPANY_ONBOARDING_SELECTION)
    company_login_email = State(STATE_COMPANY_LOGIN_EMAIL)
    company_login_password = State(STATE_COMPANY_LOGIN_PASSWORD)
    local_jobs_list = State(STATE_LOCAL_JOBS_LIST)
    local_job_detail = State(STATE_LOCAL_JOB_DETAIL)
    profile_periodo = State(STATE_PROFILE_PERIODO)
    profile_skills = State(STATE_PROFILE_SKILLS)
    profile_link = State(STATE_PROFILE_LINK)
    confirm_application = State(STATE_CONFIRM_APPLICATION)

    begin_login = (
        idle.to(login_step_ra)
        | login_step_waiting_confirmation.to(login_step_ra)
        | company_onboarding_selection.to(login_step_ra)
    )
    submit_ra = login_step_ra.to(login_step_password)
    submit_password = login_step_password.to(login_step_email)
    await_confirmation = login_step_email.to(login_step_waiting_confirmation)
    resend_confirmation = login_step_waiting_confirmation.to.itself()

    start_job_search = idle.to(course_selection)
    choose_course = course_selection.to(term_selection)
    finish_search = term_selection.to(idle)

    start_company_onboarding = idle.to(company_onboarding_selection)
    begin_company_login = company_onboarding_selection.to(company_login_email)
    begin_company_password_step = company_login_email.to(company_login_password)
    finish_company_onboarding = company_onboarding_selection.to(idle) | company_login_password.to(
        idle
    )

    open_local_jobs = idle.to(local_jobs_list)
    open_local_job_detail = local_jobs_list.to(local_job_detail)
    finish_local_jobs = local_jobs_list.to(idle) | local_job_detail.to(idle)

    start_profile_collection = local_job_detail.to(profile_periodo)
    submit_periodo = profile_periodo.to(profile_skills)
    submit_skills = profile_skills.to(profile_link)
    submit_link = profile_link.to(confirm_application)
    skip_to_confirmation = local_job_detail.to(confirm_application)
    finish_application = confirm_application.to(idle)

    cancel = (
        login_step_ra.to(idle)
        | login_step_password.to(idle)
        | login_step_email.to(idle)
        | login_step_waiting_confirmation.to(idle)
        | course_selection.to(idle)
        | term_selection.to(idle)
        | company_onboarding_selection.to(idle)
        | company_login_email.to(idle)
        | company_login_password.to(idle)
        | local_jobs_list.to(idle)
        | local_job_detail.to(idle)
        | profile_periodo.to(idle)
        | profile_skills.to(idle)
        | profile_link.to(idle)
        | confirm_application.to(idle)
    )


@dataclass(frozen=True)
class FlowState:
    """Small value object exposing normalized runtime and persisted values."""

    runtime: str

    @property
    def persisted(self) -> str | None:
        return None if self.runtime == STATE_IDLE else self.runtime


def normalize_current_action(current_action: str | None) -> str:
    """Return canonical runtime state, always falling back to idle."""
    if not current_action:
        return STATE_IDLE

    value = current_action.strip().lower()
    if value in CANONICAL_STATES:
        return value

    if value in LEGACY_STATE_ALIASES:
        return LEGACY_STATE_ALIASES[value]

    return STATE_IDLE


def normalized_flow_state(current_action: str | None) -> FlowState:
    """Build normalized runtime/persistence view for a raw database value."""
    return FlowState(runtime=normalize_current_action(current_action))


def route_for_action(current_action: str | None) -> str:
    """Resolve the route group that should handle the current state."""
    normalized = normalize_current_action(current_action)
    if normalized in AUTH_ROUTE_STATES:
        return ROUTE_AUTH
    if normalized in JOB_ROUTE_STATES:
        return ROUTE_JOB_SEARCH
    if normalized in COMPANY_ROUTE_STATES:
        return ROUTE_COMPANY
    if normalized in LOCAL_JOBS_ROUTE_STATES:
        return ROUTE_LOCAL_JOBS
    if normalized in APPLICATION_ROUTE_STATES:
        return ROUTE_APPLICATION
    return ROUTE_IDLE


def is_waiting_confirmation(current_action: str | None) -> bool:
    return normalize_current_action(current_action) == STATE_LOGIN_STEP_WAITING_CONFIRMATION


def has_active_flow(current_action: str | None) -> bool:
    return route_for_action(current_action) != ROUTE_IDLE


def apply_state_transition(
    *,
    conversation_state,
    next_state: str,
    clear_flow_data: bool = False,
    update_fields: list[str] | None = None,
) -> None:
    """Persist state transition using canonical values."""
    state = normalized_flow_state(next_state)
    conversation_state.current_action = state.persisted
    if clear_flow_data:
        conversation_state.flow_data = {}

    fields = ["current_action", "updated_at"]
    if clear_flow_data:
        fields.insert(1, "flow_data")
    if update_fields:
        fields.extend(update_fields)

    unique_fields = list(dict.fromkeys(fields))
    conversation_state.save(update_fields=unique_fields)
