# Copyright 2017 Glen Harmon

import logging

import sublime

from .lib.detect_syntax import AutoSyntaxDetection  # noqa
from .lib.format_ import DashFormatMacCommand  # noqa
from .lib.format_ import (ColonFormatMacCommand, DotFormatMacCommand,
                          FormatMacCommand)
from .lib.increment import (DecrementIpCommand, DecrementNetworkCommand,
                            DecrementSubnetCommand, IncrementIpCommand,
                            IncrementNetworkCommand, IncrementSubnetCommand)
# from .lib.passwords import PasswordDecryptViewListener, DecodePasswordCommand  # noqa
from .lib.passwords import DecodePasswordCommand  # noqa
from .lib.search.network import FindSubnetCommand, NetworkInfoListener  # noqa
from .lib.settings import ToggleNetworkInfoOnHoverCommand  # noqa

logger = logging.getLogger("network_tech")
logger.handlers = []

settings = sublime.load_settings("network_tech.sublime-settings")

log_level = settings.get("log_level", "warning") or "warning"
logger.setLevel(getattr(logging, log_level.upper()))


class SearchHistory(list):
    @property
    def last(self):
        last = None
        if self:
            last = self[0]
        return last
