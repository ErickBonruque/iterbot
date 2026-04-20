from dataclasses import dataclass

from config._helpers import _get_secret_or_env, env


@dataclass
class AwsSettings:
    access_key_id: str
    secret_access_key: str
    default_region: str

    def __init__(self) -> None:
        self.access_key_id = _get_secret_or_env("aws_access_key_id", "AWS_ACCESS_KEY_ID", "")
        self.secret_access_key = _get_secret_or_env(
            "aws_secret_access_key", "AWS_SECRET_ACCESS_KEY", ""
        )
        self.default_region = env("AWS_DEFAULT_REGION")
