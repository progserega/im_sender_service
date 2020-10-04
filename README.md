Система рассылки уведомлений через IM с API-сервисом.

On english:
System for sending notifications via chat with the API service.

** Im / im im (matrix)**
Notification distribution system.

The logic of the system is as follows:

- Im im (matrix)
- users are connected to it, im im (matrix)
- in the system, they also have a user on whose behalf the mailing is carried out (@bot:corp.ru)
- The author of any system that should be used for mailing takes the API key from the system administrator of the mailing service
- and configures its system to send JSON data (one of the fields must contain the previously received API key) with the information to be sent. Data in the JSON text format must contain the parcel and the recipient's address.
- the recipient's address can consist of two fields: email address and email address.
- the logic for sending mailings to these addresses is as follows: first, it tries to send a message via chat, but if you can't send it within 20 minutes, we send it by mail. If the address is not specified in principle, it is sent to the mail immediately. Attempts to send by mail servsi undertakes within 3 hours. If you can't send it, failed "failed".
- im im (matrix) - marked in the mailing status for this message
- each status change in the mailing list is marked -" in progress", "sent", "sent", "read", etc.
- when applying for the newsletter requesting system may transmit the field "callback_url" containing a link at which the mailing system will notify you of changes by sending this message sending this link to JSON data with the information in this newsletter
- when prompted for a newsletter, requesting a service may pass as your internal identifier of this message (it is stored in the database of mailing and will return when callback)
- call back s can be somewhat. Call callback-a for this message with all statuses on it.

**Sending**

Input:
* api_key** - API access key (string, required parameter-request from the API service hoster)
* **address_im** - to the recipient's address in the service (string, must be specified, or must be specified address_email, or both)
* *address_email** - recipient's email address (string, must be specified, add address_im, or both)
* **message** - message text
* **type** - message text type (string, optional parameter. Possible values: HTML, text)
* **callback_url** - web address of the callback (string, optional parameter. The service will send the message distribution status to this address when it is updated) - J JSON
* **sender_uniq_id** - unique ID of sending (string, optional parameter. This ID is saved in the mailing list database and you can use it to get the message's mailing status)
* **edit_previous** - optional option (false by default) that enables editing of previous sent messages with the same sender_uniq_id. (value: TRUE/false). If true - if the database has a previous successfully sent message with the same sender_uniq_id, then instead of sending a new message, the system will correct the text of the previous message in the chat room to a new one. In this case, the chat will show the PostScript "edited". This message will also have the status * * edited_previous_sended_by_im**

Output:
* **message_id** - internal ID of the message in the queue to be sent (integer)
* **status** - sending status (string, "success" error "error")
* **description** - detailed description in case of an error (string)

Request example:

By this URL:

https://api-sending-messages.corp.ru/api_add_message.cgi

we send it in JSON in the form:
```
{'address_im':'@user:matrix-server.com', 'message':'test message', 'api_key':'secret_api_key'}
```
Or:
```
{'address_email':'user@mail.com', 'message':'test message', 'api_key':'secret_api_key'}
```
Or:
```
{
'address_im': '@user:matrix-server.com',
'address_email':'user@mail.com',
'message':' < P>to test in HTML message: < / P><ol><Li>first< / Li><Li>second< / Li><Li>third< / Li>\n< / PR>',
'Type': 'HTML code',
'api_key': 'secret_api_key',
'sender_uniq_id': '23443',
'callback_url':'http://my-server.com/status_sending.php'
}
```


In response, the server will send the message ID, J JSON:
```
{
'message_id': 23,
"status": "success",
'description': 'add a message to the sending queue'
}
```

If an error occurs:
```
{
"status": "error",
"description": "some mistake",
}
```
** Receiving notification of the sending status **

Url "callback" url-and the service will send (several times) a JSON containing updated information on the status of sending and reading the message.

Data in JSON that the service will send:
* id-internal ID of the message in the queue to be sent (integer)
* sending_status - sending status (string, see below for status options)
* address_im-im im
* address_email-recipient's email Address
* time_create-time when the message was generated
* time_start_process-time when the sender started processing the message
* time_send-time when the message was sent
* time_read-time when the recipient reads the message
* sending_retry_num-Number of attempts to send the message
* sender_uniq_id-ID Passed from the sender to identify the message
* error_description_im-Text description of the error in sending them
* error_description_email-Text description of the email error
* callback_status-callback Status of sending information about the mailing list by
* callback_retry_num-callback Number of attempts to send information by
* im_event_id - Internal ID of the message in the instant messaging system

The status of sending a message ('sending_status') can take the following values:
* "new" - a New message to send
* "no_room" - you Need to create a room to communicate with the user
* "in progress" - in the process of sending
* 'sending_by_im' - im im
* 'sending_by_email' - Sent by mail
* 'sent_by_im' - im im
* 'sent_by_email' - Sent by mail
* "read" - Read by the recipient
* "error" - sending Failed, but attempts to resend continue
* "error" - sending Failed, attempts to resend stopped

The status of sending a callback ('callback_status') can take the following values:
* 'new' - ' Newly created request -back callback
* "need to send" - the status of sending the message has been updated. You must notify the recipient via a callback
* 'sent' - the status of sending the message was successfully sent to the recipient via collback
* "error" - sending Failed, but attempts to resend continue
* "error" - sending Failed, attempts to resend stopped


Example of the received JSON:

Successful submission:
```
{
"address_email": null,
"address_im": "@user:corp.ru",
"callback_retry_num": 3,
"callback_status": "error",
"error_description_email": null,
"error_description_im": null,
"im_event_id": "$7gFwqkL324525433WEw2pUyHzwhZ1XMAyrzgjpd6aek",
"message_id": 3,
"sender_uniq_id": null,
"sending_retry_num": 1,
"sending_status": "read",
"time_create": "2020-05-21 10: 46:40.605750",
"time_read": "2020-05-21 15: 03:14",
"time_send": "2020-05-21 10: 47: 01",
"time_start_process": "2020-05-21 10: 46:59"
}
```
Complete sending failure:
```
{
"address_email": null,
"address_im": "@user:corp.ru",
"callback_retry_num": 0,
"callback_status": "error",
"error_description_email": null,
"error_description_im": "im im im-contact the administrator",
"im_event_id": null,
"message_id": 1,
"sender_uniq_id": null,
"sending_retry_num": 1,
"sending_status": "error",
"time_create": "2020-05-20 19: 08:12.899453",
"time_read": zero,
"time_send": "2020-05-20 19: 08: 50",
"time_start_process": "2020-05-20 19: 08:49"
}
```

НА русском:

**Рассылка уведомлений через почту и/или IM (Matrix)**
Система рассылки уведомлений.

Логика работы системы следующая:

  - Есть сервер IM (matrix)
  - к нему подключены пользователи, у них есть адреса в системе IM (matrix)
  - в системе IM так же заведён пользователь, от имени которого проводится рассылка (@bot:corp.ru)
  - Автор какой-либо системы, с которой необходимо проводить рассылку берёт у системного администратора сервиса рассылки API-ключ
  - и настраивает свою систему, чтобы она по необходимости рассылки - отправляла json-данные (одно из полей должно содержать полученный ранее API-ключ) с информацией, которую нужно отправить. Данные json должны содержать текст посылки, адрес получателя.
  - адрес получателя может состоять из двух полей - IM-адреса и почтового.
  - логика отправки у рассылки по этим адресам следующая: сначала пытается отправить сообщение через IM, если же в течении 20 минут не получилось отправить - отправляем по почте. Если же адрес IM в принципе не указан, то на почту отправляется сразу. Попытки отправить по почте сервси предпринимает в течении 3-х часов. Если же отправить не удалось, то статус у этого запроса приобретает наименование 'failed'.
  - ошибки отправки по почте и через IM (matrix) - помечаются в статусе рассылки для этого сообщения
  - каждое изменение статуса в рассылке сообщения помечается - "в процессе", "отправляется", "отправилось", "прочитано" и т.п.
  - при подаче заявки на рассылку запрашивающая система может передать поле "callback_url", содержащее ссылку, по которой система рассылки будет уведомлять об изменениях по рассылке данного сообщения, отправляя по этой ссылке json-данные с информацией по данной рассылке
  - при запросе на рассылку, запрашивающий сервис может передать так же свой внутренний идентификатор этого сообщения (он сохранится в базе рассылки и вернётся при callback)
  - callback-ов может быть несколько. Каждое изменение статуса рассылки провоцирует отправку callback-а для данного сообщения со всеми статусами по нему.

**Отправка**

Входные данные:
  * **api_key** - ключ доступа к АПИ (строка, обязательный параметр - запросить у хостера АПИ-сервиса)
  * **address_im** - адрес получателя в IM сервисе (строка, должен быть указан, либо должен быть указан address_email, либо оба)
  * **address_email** - почтовый адрес получателя (строка, должен быть указан, либо должен быть указан address_im, либо оба)
  * **message** - текст сообщения
  * **type** - тип текста сообщения (строка, необязательный параметр. Возможные значения: html, text)
  * **callback_url** - web-адрес обратного вызова (строка, необязательный параметр. По данному адресу сервис будет отправлять статус рассылки сообщения при его обновлении) - отправляться будет json
  * **sender_uniq_id** - уникальный идентификатор отправки (строка, необязательный параметр. Этот идентификатор сохраняется в базе рассылки и по нему можно получить статус рассылки сообщения)
  * **edit_previouse** - необязательная опция (по-умолчанию - False), включающая редактирование предыдущих отправленных сообщений с таким же sender_uniq_id. (значение: True/False). В случае True - если в базе есть предыдущее успешно отправленное сообщение с таким же sender_uniq_id, то вместо отправки нового сообщения - система исправит текст предыдущего сообщения в комнате чата на новый. При этом чат покажет приписку "отредактировано". У этого сообщения же станет статус **edited_previous_sended_by_im**

Выходные данные:
  * **message_id** - внутренний идентификатор сообщения в очереди на отправку (целое число)
  * **status** - статус отправки (строка, "success" или "error")
  * **description** - детальное описание в случае ошибки (строка)

Пример запроса:

По данному url:

https://api-sending-messages.corp.ru/api_add_message.cgi

отпраляем json вида:
```
{'address_im':'@user:matrix-server.com','message':'test message', 'api_key':'secret_api_key'}
```
Или:
```
{'address_email':'user@mail.com','message':'test message', 'api_key':'secret_api_key'}
```
Или:
```
{
  'address_im':'@user:matrix-server.com',
  'address_email':'user@mail.com',
  'message':'<p>test html-message: </p><ol><li>первое</li><li>второе</li><li>третье</li>\n</ol>',
  'type':'html',
  'api_key':'secret_api_key',
  'sender_uniq_id':'23443',
  'callback_url':'http://my-server.com/status_sending.php'
}
```

 
В ответ сервер пришлёт идентификатор сообщения, в виде json:
```
{
  'message_id':23,
  'status': 'success',
  'description': 'add message to sending queue'
}
```

В случае ошибки:
```
{
  "status": "error",
  "description": "some error",
}
```
** Получение уведомления о статусе отправки **

По указанному в запросе url "callback"-а сервис отправит (несколько раз) json, содержащий обновляему информацию по статусу отправки и прочтения сообщения.

Данные в json, который отправит сервис:
  * id - внутренний идентификатор сообщения в очереди на отправку (целое число)
  * sending_status - статус отправки (строка, варианты статусов см. ниже)
  * address_im - Адрес пользователя в IM
  * address_email - Адрес электронной почты получателя
  * time_create - Время формирования сообщения
  * time_start_process - Время начала обработки сообщения отправщиком
  * time_send - Время отправки сообщения
  * time_read - Время прочтения сообщения получателем
  * sending_retry_num - Количество попыток отправки сообщения
  * sender_uniq_id - Идентификатор, переданный от отправителя, для идентификации сообщения
  * error_description_im - Текстовое описание ошибки отправки по IM
  * error_description_email - Текстовое описание ошибки отправки по почте
  * callback_status - Статус отправки информации о рассылке по callback
  * callback_retry_num - Количество попыток отправок информации по callback
  * im_event_id - Внутренний идентификатор сообщения в системе IM

Статус отправки сообщения ('sending_status') может принимать значения:
  * 'new' - Новое сообщение для отправки
  * 'no_room' - Необходимо создать комнату для общения с пользователем
  * 'in progress' - В процессе отправки
  * 'sending_by_im' - Отправляется через IM
  * 'sending_by_email' - Отправляется по почте
  * 'sent_by_im' - Отправлено через IM
  * 'sent_by_email' - Отправлено по почте
  * 'readed' - Прочитано получателем
  * 'error' - Сбой отправки, но попытки повторной отправки продолжаются
  * 'fault' - Сбой отправки, попытки повторной отправки прекращены

Статус отправки callback ('callback_status') может принимать значения:
  * 'new' - 'Вновь созданный запрос - пока нет необходимости слать информацию по callback
  * 'need send' - Статус отправки сообщения обновлён. Необходимо уведомить об этом получаетя через callback
  * 'sended' - Статус отправки сообщения успешно отправлен получателю по collback
  * 'error' - Сбой отправки, но попытки повторной отправки продолжаются
  * 'fault' - Сбой отправки, попытки повторной отправки прекращены


Пример получаемого json:

Успешная отправка:
```
 {
    "address_email": null,
    "address_im": "@user:corp.ru",
    "callback_retry_num": 3,
    "callback_status": "error",
    "error_description_email": null,
    "error_description_im": null,
    "im_event_id": "$7gFwqkL324525433WEw2pUyHzwhZ1XMAYRZgJpd6aEk",
    "message_id": 3,
    "sender_uniq_id": null,
    "sending_retry_num": 1,
    "sending_status": "readed",
    "time_create": "2020-05-21 10:46:40.605750",
    "time_read": "2020-05-21 15:03:14",
    "time_send": "2020-05-21 10:47:01",
    "time_start_process": "2020-05-21 10:46:59"
}
```
Полный сбой отправки:
```
{
    "address_email": null,
    "address_im": "@user:corp.ru",
    "callback_retry_num": 0,
    "callback_status": "error",
    "error_description_email": null,
    "error_description_im": "ошибка заведения комнаты в IM для посылки сообщения - обратитесь к администратору",
    "im_event_id": null,
    "message_id": 1,
    "sender_uniq_id": null,
    "sending_retry_num": 1,
    "sending_status": "fault",
    "time_create": "2020-05-20 19:08:12.899453",
    "time_read": null,
    "time_send": "2020-05-20 19:08:50",
    "time_start_process": "2020-05-20 19:08:49"
}
```


