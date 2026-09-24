import enum


class TaxRegime(str, enum.Enum):
    standard = "standard"
    small_business = "small_business"
    micro_business = "micro_business"


class TransactionDirection(str, enum.Enum):
    income = "income"
    expense = "expense"


class TaxEventStatus(str, enum.Enum):
    pending = "pending"
    filed = "filed"
    paid = "paid"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
