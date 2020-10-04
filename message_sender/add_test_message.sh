#!/bin/bash
echo '{"api_key":"XXXXX", "message":"тестовое сообщение from bash call python add.cgi", "address_im":"@user:corp.ru"}'|./api_add_message.py
#echo '{"api_key":"XXXX", "message":"<p>test markdown: <code>code</code>,</p><ol><li>первое</li><li>второе</li><li>третье</li>\n</ol>","type":"html","address_im":"@user:corp.ru"}'|./api_add_message.py
