from pydantic import BaseModel, AnyUrl

class GitConfig(BaseModel):
    git_url: AnyUrl


