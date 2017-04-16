# -*- coding: utf-8 -*-

import socket
import struct

import pytest

from pingem import pinger as tested


def have_raw_socket_capability():
    try:
        socket.socket(socket.AF_INET, socket.SOCK_RAW, tested.ICMP)
    except socket.error:
        return False
    else:
        return True


@pytest.mark.skipif(
    not have_raw_socket_capability(),
    reason='Cannot open raw sockets'
)
class TestPinger(object):

    def setup(self):
        self.tested = tested.Pinger(self.callback, timeout=0.1)
        self.replies = {}

    def callback(self, host, rtt):
        self.replies[host] = rtt

    def test_ping__calls_back_with_host_and_rtt(self):
        self.tested.add_host('127.0.0.1')

        self.tested.ping()

        assert self.replies['127.0.0.1']

    def test_ping__calls_back_with_rtt_None_if_no_reply(self):
        self.tested.add_host('1.1.1.1')

        self.tested.ping()

        assert self.replies['1.1.1.1'] is None

    def test_ping__multiple_hosts(self):
        self.tested.add_host('127.0.0.1')
        self.tested.add_host('www.google.com')

        self.tested.ping()

        assert self.replies.pop('127.0.0.1')
        assert self.replies.pop('www.google.com')
        assert not self.replies

    def test_ping__thousands_of_hosts(self):
        first_host_int = struct.unpack("!I", socket.inet_aton('127.0.0.1'))[0]
        for i in range(10000):
            ip = socket.inet_ntoa(struct.pack("!I", first_host_int + i))
            self.tested.add_host(ip)

        self.tested.ping()

        assert len(self.replies) == 10000
        assert all(self.replies.values())

    def test_ping__reuses_added_hosts_on_second_call(self):
        self.tested.add_host('127.0.0.1')
        self.tested.ping()
        self.replies.clear()

        self.tested.ping()

        assert self.replies['127.0.0.1']

    def test_clear_hosts__removes_hosts_for_next_ping_call(self):
        self.tested.add_host('127.0.0.1')
        self.tested.clear_hosts()

        self.tested.ping()

        assert not self.replies
