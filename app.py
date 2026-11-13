import streamlit as st
from dotenv import load_dotenv

from email_sender import is_valid_email_address
from workflow import MODEL_NAME, build_workflow


load_dotenv()
st.set_page_config(page_title="Email workflow", page_icon=":material/mail:", layout="wide")
st.title("Email workflow")
st.caption(
    "Describe the email and choose its recipient. Gemini plans, drafts, and reviews it; "
    "the workflow sends it only when the review approves the draft."
)

NODE_INFO = [
    ("plan", "Plan", "Organize the request."),
    ("draft", "Draft email", "Write the subject and message."),
    ("review", "Review", "Check the draft before sending."),
    ("send", "Send email", "Send through Gmail SMTP."),
    ("status", "Final status", "Confirm SENT, NEEDS_REVIEW, or FAILED."),
]
NODE_TITLES = {key: title for key, title, _ in NODE_INFO}


def render_flow(card_slots, step_states: dict[str, str]) -> None:
    icons = {
        "active": ":material/pending:",
        "complete": ":material/check_circle:",
        "failed": ":material/error:",
        "skipped": ":material/skip_next:",
        "waiting": ":material/radio_button_unchecked:",
    }
    labels = {
        "active": "ACTIVE",
        "complete": "DONE",
        "failed": "FAILED",
        "skipped": "SKIPPED",
        "waiting": "WAITING",
    }
    for slot, (key, title, description) in zip(card_slots, NODE_INFO):
        state = step_states.get(key, "waiting")
        with slot.container(border=True):
            st.markdown(f"**{title}**")
            st.markdown(f"{icons[state]} {labels[state]}")
            st.caption(description)


st.subheader("Live workflow")
flow_columns = st.columns(
    [0.55, 2, 0.35, 2, 0.35, 2, 0.35, 2, 0.35, 2, 0.55],
    vertical_alignment="center",
)
flow_columns[0].markdown("**START**")
flow_columns[2].markdown("→")
flow_columns[4].markdown("→")
flow_columns[6].markdown("→")
flow_columns[8].markdown("→")
flow_columns[10].markdown("**END**")
card_slots = [flow_columns[index].empty() for index in (1, 3, 5, 7, 9)]
render_flow(card_slots, {})

with st.form("email_workflow"):
    recipient = st.text_input(
        "Who should receive the email?",
        placeholder="recipient@example.com",
    )
    task = st.text_area(
        "What should the email say?",
        placeholder="For example: Thank Alex for the meeting and ask if Tuesday afternoon works for a follow-up.",
        height=120,
    )
    submitted = st.form_submit_button(
        "Draft, review and send email",
        type="primary",
        icon=":material/send:",
        width="stretch",
    )

if submitted:
    recipient = recipient.strip()
    task = task.strip()
    if not is_valid_email_address(recipient):
        st.warning("Enter a valid recipient email address.")
    elif not task:
        st.warning("Describe the email before starting the workflow.")
    else:
        state = {
            "task": task,
            "recipient": recipient,
            "steps": {},
        }
        status_box = st.status("Starting workflow…", expanded=True)
        try:
            graph = build_workflow()
            for event in graph.stream(state, stream_mode="tasks"):
                node_name = event.get("name", "")
                if "input" in event and node_name in NODE_TITLES:
                    step_states = dict(state.get("steps", {}))
                    step_states[node_name] = "active"
                    state["steps"] = step_states
                    status_box.update(
                        label=f"Working: {NODE_TITLES[node_name]}",
                        state="running",
                        expanded=True,
                    )
                    render_flow(card_slots, step_states)
                elif "result" in event:
                    state.update(event.get("result") or {})
                    render_flow(card_slots, state.get("steps", {}))
                elif event.get("error"):
                    raise RuntimeError("A workflow step failed.")

            status_box.update(
                label=f"Workflow finished: {state.get('status', 'UNKNOWN')}",
                state="error" if state.get("status") == "FAILED" else "complete",
                expanded=False,
            )
        except Exception as error:
            state["status"] = "FAILED"
            state["send_error"] = str(error)
            active_step = next(
                (key for key, value in state.get("steps", {}).items() if value == "active"),
                None,
            )
            if active_step:
                state["steps"][active_step] = "failed"
            status_box.update(label="Workflow failed", state="error", expanded=True)
            render_flow(card_slots, state.get("steps", {}))

        if state.get("status") == "SENT":
            st.success(f"Email sent to {recipient}.", icon=":material/check_circle:")
            st.toast(f"Email sent to {recipient}.", icon=":material/mark_email_read:")
        elif state.get("status") == "NEEDS_REVIEW":
            st.warning(
                "The draft did not pass review, so it was not sent.",
                title="Needs review",
            )
        else:
            st.error(
                state.get("send_error", "The email was not sent."),
                title="Email not sent",
            )

        if state.get("subject"):
            st.subheader("Email details")
            st.write(f"**To:** {recipient}")
            st.write(f"**Subject:** {state['subject']}")
            with st.expander("View drafted message", expanded=False):
                st.text(state.get("body", ""))
            if state.get("review_feedback"):
                st.caption(f"Review: {state['review_feedback']}")

st.divider()
st.caption(f"Model: {MODEL_NAME} · Plan → Draft → Review → Send → Status")

