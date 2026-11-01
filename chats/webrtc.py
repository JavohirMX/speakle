"""ICE server list for the video room, built from settings (see config/settings.py)."""
from django.conf import settings


def _split(value):
    return [u.strip() for u in (value or '').split(',') if u.strip()]


def ice_servers():
    """Return the RTCPeerConnection `iceServers` list.

    STUN servers come first. A TURN entry is added only when URLs, username and credential
    are all set, so a half-configured TURN setting never breaks calls.
    """
    servers = []
    stun = _split(settings.WEBRTC_STUN_URLS)
    if stun:
        servers.append({'urls': stun})
    turn = _split(settings.WEBRTC_TURN_URLS)
    if turn and settings.WEBRTC_TURN_USERNAME and settings.WEBRTC_TURN_CREDENTIAL:
        servers.append({
            'urls': turn,
            'username': settings.WEBRTC_TURN_USERNAME,
            'credential': settings.WEBRTC_TURN_CREDENTIAL,
        })
    return servers
