from dotenv import load_dotenv

from email_sender import is_valid_email_address
from workflow import MODEL_NAME, build_workflow


def main() -> None:
    load_dotenv()
    recipient = input("Who should receive the email? ").strip()
    if not is_valid_email_address(recipient):
        raise SystemExit("Enter a valid recipient email address.")

    task = input("What should the email say? ").strip()
    if not task:
        raise SystemExit("Describe the email before starting the workflow.")

    try:
        result = build_workflow().invoke(
            {"task": task, "recipient": recipient, "steps": {}}
        )
    except Exception as error:
        print(f"\nStatus: FAILED\nDetails: {error}")
        raise SystemExit(1) from error

    print(f"\nModel: {MODEL_NAME}")
    print(f"To: {recipient}")
    print(f"Subject: {result.get('subject', '(no draft)')}")
    print(f"\nReview: {result.get('review_feedback', '(no review)')}")
    if result.get("status") == "SENT":
        print("\nStatus: SENT")
    elif result.get("status") == "NEEDS_REVIEW":
        print("\nStatus: NEEDS_REVIEW — email was not sent")
    else:
        print(f"\nStatus: FAILED — {result.get('send_error', 'email was not sent')}")


if __name__ == "__main__":
    main()
