#!/bin/sh
export PHP_FCGI_CHILDREN=4
export PHP_FCGI_MAX_REQUESTS=200
exec /Applications/MAMP/bin/php/php5.1.6/bin/php-cgi -c "/Library/Application Support/appsolute/MAMP PRO/conf/php5.1.6.ini"