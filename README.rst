pingem - ping multiple hosts in parallel
========================================

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
