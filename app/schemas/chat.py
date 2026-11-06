from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value):
        return value.strip() if isinstance(value, str) else value


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[ChatMessage] = Field(min_length=1, max_length=11)

    @model_validator(mode="after")
    def check_conversation(self):
        if sum(len(message.content) for message in self.messages) > 12000:
            raise ValueError("대화는 총 12,000자 이하여야 합니다.")
        if len(self.messages) % 2 != 1 or any(
            message.role != ("user" if index % 2 == 0 else "assistant")
            for index, message in enumerate(self.messages)
        ):
            raise ValueError("사용자와 도우미 메시지를 번갈아 보내고 사용자 질문으로 끝내세요.")
        if any(len(message.content) > 2000 for message in self.messages if message.role == "user"):
            raise ValueError("질문은 2,000자 이하여야 합니다.")
        return self
