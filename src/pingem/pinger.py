# -*- coding: utf-8 -*-

# Copyright (c) 2017 Sander Ernes.
# License: MIT, see LICENSE for more details.

# ICMP packet construction, parsing, checksumming blatantly taken from
# python-ping

import array
import socket
import struct
import sys
import time

import pyev

ICMP = socket.getprotobyname('icmp')
ICMP_ECHO_REPLY = 0
ICMP_ECHO_REQUEST = 8

ICMP_HEADER_FORMAT = '!BBHHH'  # type, code, checksum, id, seq
ICMP_HEADER_SIZE = struct.calcsize(ICMP_HEADER_FORMAT)
ICMP_TIMESTAMP_SIZE = struct.calcsize('d')


class Pinger(object):
    """Ping multiple hosts in parallel

    Args:
        callback (callable): a callback taking (host, rtt) as arguments
        timeout (float): number of seconds to wait for a reply
        packet_limit (int): number of concurrently 'active' packets
        packet_size (int): ICMP packet size

    Sample usage::

        >>> from pingem import Pinger
        >>> def print_reply(host, rtt):
        ...     print host, rtt
        ...
        >>> pinger = Pinger(print_reply)
        >>> pinger.add_host('127.0.0.1')
        >>> pinger.add_host('www.google.com')
        >>> pinger.ping()
        127.0.0.1 0.000344038009644
        www.google.com 0.0753450393677
    """

    def __init__(self, callback=None, timeout=1.0,
                 packet_limit=1000, packet_size=64):
        self.callback = callback
        self._timeout = timeout
        self._last_packet_timestamp = 0
        self._packet_limit = packet_limit
        self._packet_size = packet_size

        self._hosts = []

        self._id = 0
        self._seq = 0
        self._pending_hosts = []
        self._packets = {}

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, ICMP)

        self._loop = pyev.Loop()
        self._io_watcher = self._loop.io(
            self._socket, pyev.EV_READ, self._on_receive
        )
        self._idle_watcher = self._loop.idle(self._on_idle)

    @property
    def callback(self):
        return self._callback

    @callback.setter
    def callback(self, value):
        self._callback = value or (lambda host, rtt: None)

    def add_host(self, host):
        """Add a host to be pinged.
        """
        self._hosts.append(host)

    def clear_hosts(self):
        """Clear hosts (affects next call to ping() if the pinger is running)
        """
        self._hosts = []

    def ping(self):
        """Ping all added hosts, calling back with the results.
        """
        self._pending_hosts = self._hosts[:]
        self._seq = (self._seq + 1) & 0xFFFF  # increment & truncate to 16 bits

        self._idle_watcher.start()
        self._io_watcher.start()
        self._loop.start()

    def _on_idle(self, watcher, revents):
        if self._pending_hosts:
            if not self._try_send():
                self._try_removing_a_timed_out_packet()
        else:
            if not self._packets or self._have_timed_out():
                self._loop.stop()
                self._send_timeouts()

    def _try_removing_a_timed_out_packet(self):
        now = time.time()
        for packet_id, packet in self._packets.iteritems():
            if now - packet['send_time'] > self._timeout:
                self._callback(packet['dst_addr'], None)
                del self._packets[packet_id]
                return

    def _try_send(self):
        if len(self._packets) < self._packet_limit:
            self._send(self._pending_hosts.pop())
            return True

    def _have_timed_out(self):
        return time.time() - self._last_packet_timestamp > self._timeout

    def _send_timeouts(self):
        for packet in self._packets.itervalues():
            self._callback(packet['dst_addr'], None)
        self._packets.clear()

    def _send(self, dst_addr):
        packet_id = self._get_next_packet_id()
        now = time.time()

        packet = create_icmp_echo_request(
            packet_id, self._seq, now, size=self._packet_size
        )

        self._socket.sendto(packet, (dst_addr, 1))
        self._packets[packet_id] = {
            'dst_addr': dst_addr,
            'send_time': now
        }
        self._last_packet_timestamp = now

    def _get_next_packet_id(self):
        packet_id = self._id
        self._id = (self._id + 1) & 0xFFFF  # increment & truncate to 16 bits
        return packet_id

    def _on_receive(self, watcher, revents):
        received_packet, addr = self._socket.recvfrom(1024)
        try:
            packet_id, seq, time_sent = parse_icmp_echo_reply(received_packet)
        except InvalidIcmpPacketType:
            return

        if seq != self._seq:
            return

        try:
            packet = self._packets.pop(packet_id)
        except KeyError:
            return

        rtt = time.time() - time_sent

        self._callback(packet['dst_addr'], rtt)


class InvalidIcmpPacketType(Exception):
    pass


def create_icmp_echo_request(id_, seq, timestamp, size=64):
    """Create an ICMP echo request packet

    Args:
        id_ (int): packet id
        seq (int): sequence id
        timestamp (int): timestamp to include in the packet
        size (int): packet size
    """
    payload_psize = size - ICMP_HEADER_SIZE
    checksum = 0

    header = struct.pack(
        ICMP_HEADER_FORMAT, ICMP_ECHO_REQUEST, 0, checksum, id_, seq
    )
    payload = (payload_psize - ICMP_TIMESTAMP_SIZE) * 'Q'
    payload = struct.pack('d', timestamp) + payload

    checksum = calculate_checksum(header + payload)

    header = struct.pack(
        ICMP_HEADER_FORMAT, ICMP_ECHO_REQUEST, 0, checksum, id_, seq
    )

    return header + payload


def parse_icmp_echo_reply(packet):
    """Parse echo reply from a **raw** ICMP `packet`.

    Raise:
        InvalidIcmpPacketType: if the packet is not an ICMP echo reply.

    Returns:
        Tuple of (packet_id, sequcene_id, timestamp).
    """
    type_, code, checksum, id_, seq = struct.unpack(
        ICMP_HEADER_FORMAT, packet[20:28]
    )

    if type_ != ICMP_ECHO_REPLY:
        raise InvalidIcmpPacketType('Packet is not ICMP echo reply')

    timestamp = struct.unpack('d', packet[28:28 + ICMP_TIMESTAMP_SIZE])[0]

    return id_, seq, timestamp


def calculate_checksum(source_string):
    if len(source_string) % 2:
        source_string += '\x00'

    converted = array.array('H', source_string)

    if sys.byteorder == 'big':
        converted.byteswap()

    val = sum(converted)

    val &= 0xffffffff  # Truncate val to 32 bits (a variance from ping.c, which
                       # uses signed ints, but overflow is unlikely in ping)

    val = (val >> 16) + (val & 0xffff)    # Add high 16 bits to low 16 bits
    val += (val >> 16)                    # Add carry from above (if any)
    answer = ~val & 0xffff                # Invert and truncate to 16 bits
    answer = socket.htons(answer)

    return answer
