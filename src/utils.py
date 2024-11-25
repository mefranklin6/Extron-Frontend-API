from extronlib.system import Ping, ProgramLog, SetAutomaticTime


def set_ntp(ntp_primary, ntp_secondary=None):
    success_count, fail_count, rtt = Ping(ntp_primary, count=1)
    if success_count > 0:
        SetAutomaticTime(ntp_primary)
        ProgramLog("Set NTP to primary server at {}".format(ntp_primary), "info")
        ProgramLog("NTP Primary RTT: {}".format(rtt), "info")
        return
    if ntp_secondary:
        success_count, fail_count, rtt = Ping(ntp_secondary, count=1)
        if success_count > 0:
            SetAutomaticTime(ntp_secondary)
            ProgramLog("Set NTP to secondary server at {}".format(ntp_secondary), "info")
            return
        else:
            ProgramLog("NTP servers are unreachable", "error")

def log(message, level="info"):
    """
    Logs a message with a given severity level.

    Parameters:
    message (str): The message to log.
    level (str): The severity level of the log. Options are: info, warning, error.
    """

    # Log internally and allow for future log forwarding
    ProgramLog(str(message), level)