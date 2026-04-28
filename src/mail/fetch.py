import os
from dotenv import load_dotenv
from imap_tools import MailBox, AND


def main():
    load_dotenv()
    host = os.environ["IMAP_HOST"]
    user = os.environ["IMAP_USER"]
    password = os.environ["IMAP_PASSWORD"]
    folder = os.getenv("IMAP_FOLDER", "INBOX")

    with MailBox(host).login(user, password, initial_folder=folder) as mailbox:
        for msg in mailbox.fetch(AND(all=True), limit=10, reverse=True):
            print(f"{msg.date} | {msg.from_} | {msg.subject}")


if __name__ == "__main__":
    main()
