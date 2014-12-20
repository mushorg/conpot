# https://www.bountysource.com/issues/4335201-ssl-broken-for-python-2-7-9
# Kudos to Eugene for this workaround!
def fix_sslwrap():
    # Re-add sslwrap to Python 2.7.9
    import inspect
    __ssl__ = __import__('ssl')

    try:
        _ssl = __ssl__._ssl
    except AttributeError:
        _ssl = __ssl__._ssl2

    def new_sslwrap(sock, server_side=False, keyfile=None, certfile=None, cert_reqs=__ssl__.CERT_NONE, ssl_version=__ssl__.PROTOCOL_SSLv23, ca_certs=None, ciphers=None):
        context = __ssl__.SSLContext(ssl_version)
        context.verify_mode = cert_reqs or __ssl__.CERT_NONE
        if ca_certs:
            context.load_verify_locations(ca_certs)
        if certfile:
            context.load_cert_chain(certfile, keyfile)
        if ciphers:
            context.set_ciphers(ciphers)

        caller_self = inspect.currentframe().f_back.f_locals['self']
        return context._wrap_socket(sock, server_side=server_side, ssl_sock=caller_self)

    if not hasattr(_ssl, 'sslwrap'):
        _ssl.sslwrap = new_sslwrap