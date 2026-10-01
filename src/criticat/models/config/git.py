from pydantic import AnyUrl, BaseModel


class GitConfig(BaseModel):
    git_url: AnyUrl
