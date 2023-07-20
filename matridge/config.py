MAX_HISTORY_FETCH = 100
MAX_HISTORY_FETCH__DOC = (
    "Number of events to fetch to back-fill MUC history before slidge starts up."
)

MAX_PARTICIPANTS_FETCH = 10
MAX_PARTICIPANTS_FETCH__DOC = (
    "Number of participants to fetch when joining a group. "
    "Higher values will make joining slower, and participants will appear when "
    "they speak or if they spoke in the back-filled events. "
    "Participants with power levels > 50 (ie, admins) will be fetched."
)
