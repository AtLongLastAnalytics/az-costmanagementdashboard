"""External clients for the weekly report (Key Vault + ACS email)."""

from __future__ import annotations


def read_secret(vault_uri: str, name: str) -> str:  # pragma: no cover
    """Read a secret value from Key Vault using managed identity."""
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    client = SecretClient(vault_uri, DefaultAzureCredential())
    return client.get_secret(name).value or ""


def send_email(  # pragma: no cover
    connection_string: str,
    sender: str,
    recipient: str,
    subject: str,
    text: str,
    html: str,
) -> None:
    """Send an email via Azure Communication Services."""
    from azure.communication.email import EmailClient

    client = EmailClient.from_connection_string(connection_string)
    message = {
        "senderAddress": sender,
        "recipients": {"to": [{"address": recipient}]},
        "content": {"subject": subject, "plainText": text, "html": html},
    }
    client.begin_send(message)
