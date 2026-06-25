"""
email_parser.py

Parses a single raw Enron email file into a structured dictionary
using Python's built-in `email` module.
"""

import email
from email import policy
from pathlib import Path


def parse_email_file(file_path: str) -> dict:
    """
    Reads a single raw email file and extracts key fields.

    Args:
        file_path: path to the raw email .txt file

    Returns:
        A dictionary with keys: message_id, from_addr, to_addrs,
        cc_addrs, subject, date, body
    """
    path = Path(file_path)

    # Read the raw file as bytes — using 'rb' avoids encoding errors,
    # since some Enron emails have weird/legacy character encodings.
    with open(path, "rb") as f:
        raw_bytes = f.read()

    # email.message_from_bytes() parses the raw text into a structured
    # Message object. `policy.default` gives us modern, easier-to-use
    # header access (instead of the old legacy API).
    msg = email.message_from_bytes(raw_bytes, policy=policy.default)

    # --- Extract headers ---
    message_id = msg.get("Message-ID", "").strip()
    from_addr = msg.get("From", "").strip()
    subject = msg.get("Subject", "").strip()
    date = msg.get("Date", "").strip()

    # 'To' and 'Cc' can contain multiple comma-separated addresses.
    # We split them into a clean list. If the header is missing, default to [].
    to_raw = msg.get("To", "")
    to_addrs = [addr.strip() for addr in to_raw.split(",") if addr.strip()]

    cc_raw = msg.get("Cc", "")
    cc_addrs = [addr.strip() for addr in cc_raw.split(",") if addr.strip()]
    x_folder = msg.get("X-Folder", "").strip()
    x_origin = msg.get("X-Origin", "").strip()

    # --- Extract body ---
    # Enron emails are plain text, but some may technically be multipart.
    # get_body() with preferred plain text handles both simple and
    # multipart cases safely.
    body_part = msg.get_body(preferencelist=("plain",))
    if body_part is not None:
        body = body_part.get_content().strip()
    else:
        body = ""

    return {
        "message_id": message_id,
        "from_addr": from_addr,
        "to_addrs": to_addrs,
        "cc_addrs": cc_addrs,
        "subject": subject,
        "date": date,
        "body": body,
        "x_folder": x_folder,
        "x_origin": x_origin,
    }


# # --- Quick manual test when running this file directly ---
# if __name__ == "__main__":
#     import sys

#     if len(sys.argv) < 2:
#         print("Usage: python email_parser.py <path_to_email_file>")
#         sys.exit(1)

#     test_file = sys.argv[1]
#     result = parse_email_file(test_file)

#     for key, value in result.items():
#         print(f"{key}: {value}\n")