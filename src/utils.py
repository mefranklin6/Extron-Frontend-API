import urllib.error
import urllib.request

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
            ProgramLog(
                "Set NTP to secondary server at {}".format(ntp_secondary), "info"
            )
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


def backend_server_ok(ip):
    headers = {"Content-Type": "application/json"}
    url = "{}/api/v1/{}".format(ip, "test")

    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=2) as response:
            response_data = response.read().decode()
            log("Test Response: {}".format(response_data), "info")
            if "OK" in response_data:
                log("Backend server {} is OK".format(str(ip)), "info")
                return True
            else:
                log(
                    "Backend server unknown response: {}".format(str(response_data)),
                    "error",
                )

    # Timeout
    except urllib.error.URLError as e:
        if isinstance(e.reason, urllib.error.URLError) and "timed out" in str(e.reason):
            log("Backend server {} timed out".format(str(ip)), "error")
        else:
            log("URLError: {}".format(str(e)), "error")

    except Exception as e:
        log(str(e), "error")

    return False
