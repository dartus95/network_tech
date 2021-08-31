"""
Copyright 2017 Glen Harmon

"""

import importlib
import ipaddress
import logging
import os
import re
import socket

import sublime

from .html_helper import Html
from .selection_utility import SelectionUtility
from .variables import ip

Iana = importlib.import_module("Network Tech.lib.iana").Iana
cache = importlib.import_module("Network Tech.lib.utilities").cache

# from network_tech.lib.iana import Iana

ipv4_zero_network = re.compile(r"^0\.0\.0\.0/(?:(?:3[0-2])|(?:[0-2]?\d))$")
logger = logging.getLogger("network_tech.search.network.network")


iana = Iana(os.path.sep.join(["Network Tech", "iana.cache"]))


def _ipv6_mac(network):
    """ Get the MAC address from an auto generated IPv6 address """
    # Example address used in comments: fe80::a021:27ff:fe00:d8

    address = ipaddress.ip_interface(network).ip

    # Fully written out fe80::a021:27ff:fe00:d8 → fe80:0:0:0:a021:27ff:fe00:d8

    # Remove the first 64 bits
    binary_digits = bin(int(address))[2:].zfill(128)

    removed_prefix = binary_digits[64:]

    # We now have a021:27ff:fe00:d8

    # Verify it is auto generated, bits 24-40 are 'fffe':
    if hex(int(removed_prefix[24:40], 2)).lower() != "0xfffe":
        return None

    # Flip bit 6 using a mask
    flipped_bit = "0" if removed_prefix[6] == "1" else "1"
    bit_flipped = removed_prefix[0:6] + flipped_bit + removed_prefix[7:]

    # Remove the inserted ff:fe in the middle
    mac_in_binary = bit_flipped[0:24] + bit_flipped[40:]

    mac_in_hex = hex(int(mac_in_binary, 2))

    mac_in_hex_zero_padded = mac_in_hex[2:].zfill(12)

    mac_parts = list()
    for i in range(0, len(mac_in_hex_zero_padded), 4):
        mac_parts.append(mac_in_hex_zero_padded[i : i + 4])

    return ".".join(mac_parts)


class Network:
    prefix_removals = ["host", "mask", "range"]

    @classmethod
    def info(cls, network):
        """ Returns HTML formated information about the network """
        content = ""
        if network.network.num_addresses == 1:
            content = cls._info_address(network)
        else:
            content = cls._info_network(network)
        return content

    @classmethod
    def _info_address(cls, ip):
        content = Html.div("IP: {}".format(ip.ip))
        if ip.is_link_local:
            content += "".join(
                [
                    Html.div("Link Local Address"),
                ]
            )

            link_local_mac = _ipv6_mac(ip)
            if link_local_mac is not None:
                content += "".join(
                    [
                        Html.div("Auto Generated from MAC: {}".format(link_local_mac)),
                    ]
                )

        return content

    @classmethod
    def _info_network(cls, network):
        content = ""
        neighbors = cls.get_neighbors(network)
        logger.debug("Neighbors {}".format(len(neighbors)))
        before, _, after = cls.get_neighbors(network)
        network_address = str(network.network.network_address)
        broadcast_address = str(network.network.broadcast_address)
        if network_address != broadcast_address:
            if network.version == 4:
                content = "".join(
                    [
                        Html.div("Network: {}".format(network.network)),
                        Html.div("Broadcast: {}".format(broadcast_address)),
                        Html.div(
                            "# Addresses: {}".format(network.network.num_addresses)
                        ),
                        Html.div("Masks:"),
                        Html.unordered_list(Network.masks(network)),
                    ]
                )
            else:
                content = "".join(
                    [
                        Html.div(
                            "Network: {}/{}".format(
                                network_address, network.network.prefixlen
                            )
                        ),
                    ]
                )
                if network.is_link_local:
                    content += "".join(
                        [
                            Html.div("Link Local Address"),
                        ]
                    )

                link_local_mac = _ipv6_mac(network)
                if link_local_mac is not None:
                    content += "".join(
                        [
                            Html.div(
                                "Auto Generated from MAC: {}".format(link_local_mac)
                            ),
                        ]
                    )

            if before or after:
                content += Html.div("Neighboring Networks")
            if after:
                content += Html.div(" Next: {}".format(after.network))
            if before:
                content += Html.div(" Previous: {}".format(before.network))
        return content

    @classmethod
    def rir(cls, network):
        rir = iana.get_registrar(network)
        if rir is not None:
            content = Html.div("RIR: {}".format(rir))
        else:
            content = ""
        return content

    @classmethod
    @cache.memory(expire_minutes=5, is_class_method=True)
    def ptr_lookup(cls, network):
        ip = str(ipaddress.ip_interface(network).ip)
        try:
            primary_hostname, alias_hostnames, other_ips = socket.gethostbyaddr(ip)
        except socket.herror as e:
            logger.debug("DNS Reverse Lookup Error {}".format(e))
            return Html.div("DNS: n/a")

        content = Html.div("DNS: {}".format(socket.getfqdn(primary_hostname)))

        if alias_hostnames:
            content += Html.div("DNS Aliases:")
        for hostname in alias_hostnames:
            fqdn_hostname = socket.getfqdn(hostname)
            logger.debug("Alias {} FQDN {}".format(hostname, fqdn_hostname))
            content += Html.div(fqdn_hostname)
        return content

    @classmethod
    def _neighboring_network(cls, interface, after=True):
        prefix = interface.network.prefixlen
        network = interface.network
        try:
            neighbor = (
                network.broadcast_address + 1 if after else network.network_address - 1
            )
        except ipaddress.AddressValueError:
            return None
        return ipaddress.ip_interface("{}/{}".format(neighbor, prefix))

    @classmethod
    def get_neighbors(cls, networks, neighbors=1):
        if not isinstance(networks, list):
            networks = [networks]
        if len(networks) == 0:
            raise ValueError("No network defined")

        before = cls._neighboring_network(networks[0], after=False)
        after = cls._neighboring_network(networks[-1], after=True)

        networks.insert(0, before)
        networks.append(after)

        remaining_neighbors = neighbors - 1
        if remaining_neighbors > 0:
            networks = cls.get_neighbors(networks, neighbors=remaining_neighbors)
        return networks

    @classmethod
    def get_network_region(cls, region, view):
        selection_functions = [
            lambda view, region: SelectionUtility.word(view, region),
            lambda view, region: SelectionUtility.left_word(view, region),
            lambda view, region: SelectionUtility.right_word(view, region),
            lambda view, region: SelectionUtility.left_word(view, region, repeat=2),
            lambda view, region: SelectionUtility.right_word(view, region, repeat=2),
            lambda view, region: SelectionUtility.right_word(
                view, SelectionUtility.left_word(view, region).begin(), repeat=2
            ),
        ]
        network = None
        network_region = None
        for index, selection_function in enumerate(selection_functions):
            current_network_region = selection_function(view, region)
            current_network_text = view.substr(current_network_region)
            current_network = cls.get(current_network_text)
            if current_network:
                logger.debug(
                    'Selection function #{} found network {} in text "{}". '.format(
                        index + 1,
                        current_network,
                        current_network_text,
                    )
                )
                if network is None:
                    network = current_network
                    network_region = current_network_region
                elif current_network.network.prefixlen <= network.network.prefixlen:
                    network = current_network
                    network_region = current_network_region
        return network_region

    @classmethod
    def get_network_on_cursor(cls, region, view):
        network = None
        selection_functions = [
            lambda view, region: SelectionUtility.word(view, region),
            lambda view, region: SelectionUtility.left_word(view, region),
            lambda view, region: SelectionUtility.right_word(view, region),
            lambda view, region: SelectionUtility.left_word(view, region, repeat=2),
            lambda view, region: SelectionUtility.right_word(view, region, repeat=2),
            lambda view, region: SelectionUtility.right_word(
                view, SelectionUtility.left_word(view, region).begin(), repeat=2
            ),
        ]
        for index, selection_function in enumerate(selection_functions):
            selected = selection_function(view, region)
            network_region = view.substr(selected)
            current_network = cls.get(network_region)
            if current_network:
                logger.debug(
                    'Selection function #{} found network {} in text "{}". '.format(
                        index + 1,
                        current_network,
                        network_region,
                    )
                )
                if network is None:
                    network = current_network
                elif current_network.network.prefixlen < network.network.prefixlen:
                    network = current_network
        return str(network) if network else ""

    @classmethod
    def masks(cls, interface):
        return [
            "/" + str(interface.network.prefixlen),
            str(interface.netmask),
            str(interface.hostmask),
        ]

    @classmethod
    def contains(cls, group, member):
        return int(group.network.network_address) <= int(
            member.network.network_address
        ) and int(group.network.broadcast_address) >= int(
            member.network.broadcast_address
        )

    @classmethod
    def clean(cls, network_text):
        for remove in cls.prefix_removals:
            network_text = network_text.replace(remove, "")
        network_text = network_text.strip()
        network_text = network_text.replace("  ", " ")
        return network_text

    @classmethod
    def _get_from_re_match(cls, network_text):
        network = None

        match = ip.v4.network.search(network_text)
        if match:
            ip_address = match.group("ip")
            prefix_length = match.group("prefix_length")
            netmask = match.group("netmask")
            wildcard = match.group("wildcard")
            mask = prefix_length or netmask or wildcard
            try:
                if mask:
                    network = ipaddress.ip_interface("/".join([ip_address, mask]))
                else:
                    network = ipaddress.ip_interface(ip_address)
            except ValueError:
                pass
            logger.debug(
                'Network regexp match: "{}" from {}'.format(network, match.group())
            )
            return network
        match = ip.v4.host.search(network_text)
        if match:
            ip_address = match.group("ip")
            network = ipaddress.ip_interface(ip_address)
            logger.debug(
                'Host regexp match: "{}" from {}'.format(network, match.group())
            )
            return network

        match = ip.v6.network.search(network_text)
        if match:
            network = ipaddress.ip_interface(match.group(0))
            logger.debug(
                'Host regexp match: "{}" from {}'.format(network, match.group())
            )
            return network

        match = ip.v6.host.search(network_text)
        if match:
            network = ipaddress.ip_interface(match.group(0))
            logger.debug(
                'Host regexp match: "{}" from {}'.format(network, match.group())
            )
            return network

        return network

    @classmethod
    def get(cls, network_text):
        network_text = cls.clean(network_text)
        result = None
        try:
            result = ipaddress.ip_interface(network_text.replace(" ", "/"))
        except ValueError:
            pass
        return result

    @classmethod
    def clean_region(cls, view, region):
        text = view.substr(region)
        for remove in cls.prefix_removals:
            if text.startswith(remove):
                cleaned = text.replace(remove, "").strip()
                removed_characters = len(text) - len(cleaned)
                return sublime.Region(region.begin() + removed_characters, region.end())
        return region

    @classmethod
    def clean_regions(cls, view, regions):
        cleaned = list()
        for region in regions:
            cleaned = cls.clean_region(view, region)
        return cleaned
