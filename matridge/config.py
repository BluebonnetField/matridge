MAX_HISTORY_FETCH = 100
MAX_HISTORY_FETCH__DOC = (
    "Number of events to fetch to back-fill MUC history before slidge starts up."
)

MAX_PARTICIPANTS_FETCH = 100
MAX_PARTICIPANTS_FETCH__DOC = (
    "Number of participants to fetch when joining a group. "
    "Higher values will make joining slower, and participants will appear when "
    "they talk anyway."
)

MAX_WAIT_MEMBERS_SYNC = 10
MAX_WAIT_MEMBERS_SYNC__DOC = (
    "Maximum time to wait, in seconds, to wait for group members to be synced. "
    "When reached, stop blocking group join and use whatever members could be "
    "retrieved/"
)
