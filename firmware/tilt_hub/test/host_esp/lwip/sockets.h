// Stand-in for lwIP's sockets.h on the host board: the address types, from the Mac's (or Linux's) own headers. The
// socket itself is not here yet. Tests only.
#pragma once
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
