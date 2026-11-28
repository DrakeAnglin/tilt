// Stand-in for ESP-IDF's esp_http_server.h on the host board. There is no web server on the controller: httpd_req_t is
// only the handlers' signature (main/api.h). Tests only.
#pragma once
#include "esp_err.h"
struct httpd_req {};
typedef struct httpd_req httpd_req_t;
