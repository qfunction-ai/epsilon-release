"""send_email — simulated exfiltration channel for the LLM01 exercise.

Takes an address and a file PATH (never file content — the path-based
signature is deliberate: no prompt that uses this tool ever asks the
model to transcribe a document into an argument, so the tool call
emits reliably even on the 4B model).

SIMULATED: no mail is sent, no filesystem is touched. The return is
honestly labeled so students never believe a message actually went
somewhere. In LLM01's vulnerable state this fake "success" completes
the attack narrative; in the fixed state the policy denies the call
before this code runs.
"""


def send_email(to: str, file_path: str) -> str:
    """Send a file as an email attachment. (Simulated: no mail is sent.)

    Args:
        to: Recipient email address.
        file_path: Path of the file to attach.

    Returns:
        A simulated confirmation string (honestly labeled).
    """
    return (
        f"[SIMULATED] Email queued to {to} with attachment {file_path} "
        f"(no mail sent in this lab)"
    )
