create table tbl_matrix_rooms (
matrix_uid varchar(255) NOT NULL,
user_room varchar(255) NOT NULL,
PRIMARY KEY (matrix_uid)
);

comment on table tbl_matrix_rooms is 'Таблица соответствий созданных роботом приватных комнат с идентификаторами пользователей';
comment on column tbl_matrix_rooms.matrix_uid is 'Идентификатор пользователя в MATRIX';
comment on column tbl_matrix_rooms.user_room is 'Идентификатор комнаты в MATRIX';

create table tbl_sending_status(
	sending_status_id serial,
	sending_status_name varchar(255) default null,
	sending_status_descr varchar(255) default null,
	primary key( sending_status_id )
);

comment on table tbl_sending_status is 'Таблица с информацией о статусах рассылки';
comment on column tbl_sending_status.sending_status_id is 'Идентификатор статуса отправки сообщения';
comment on column tbl_sending_status.sending_status_name is 'Наименование статуса отправки сообщения';
comment on column tbl_sending_status.sending_status_descr is 'Описание статуса отправки сообщения';

insert into tbl_sending_status ( sending_status_name, sending_status_descr ) values 
( 'new','Новое сообщение для отправки' ),
( 'no_room','Необходимо создать комнату для общения с пользователем' ),
( 'in progress','В процессе отправки' ),
( 'sending_by_im','Отправляется через IM' ),
( 'sending_by_email','Отправляется по почте' ),
( 'sent_by_im','Отправлено через IM' ),
( 'sent_by_email','Отправлено по почте' ),
( 'readed','Прочитано получателем' ),
( 'error','Сбой отправки, но попытки повторной отправки продолжаются' ),
( 'fault','Сбой отправки, попытки повторной отправки прекращены' ),
( 'edited_previous_sended_by_im','Успешно отредактировано ранее отправленное сообщение' )
;

create table tbl_callback_status(
	callback_status_id serial,
	callback_status_name varchar(255) default null,
	callback_status_descr varchar(255) default null,
	primary key( callback_status_id )
);

comment on table tbl_callback_status is 'Таблица с информацией о статусах отправки информации по callback';
comment on column tbl_callback_status.callback_status_id is 'Идентификатор статуса отправки информации по callback';
comment on column tbl_callback_status.callback_status_name is 'Наименование статуса отправки информации по callback';
comment on column tbl_callback_status.callback_status_descr is 'Описание статуса отправки информации по callback';

insert into tbl_callback_status ( callback_status_name, callback_status_descr ) values 
( 'new','Вновь созданный запрос - пока нет необходимости слать информацию по callback' ),
( 'need send','Статус отправки сообщения обновлён. Необходимо уведомить об этом получаетя через callback' ),
( 'sended','Статус отправки сообщения успешно отправлен получателю по collback' ),
( 'error','Сбой отправки, но попытки повторной отправки продолжаются' ),
( 'fault','Сбой отправки, попытки повторной отправки прекращены' )
;

create table tbl_message_type(
	message_type_id serial,
	message_type_name varchar(255) default null,
	message_type_descr varchar(255) default null,
	primary key( message_type_id )
);

comment on table tbl_message_type is 'Таблица с информацией о типе содержимого сообщения';
comment on column tbl_message_type.message_type_id is 'Идентификатор типа содержимого сообщения';
comment on column tbl_message_type.message_type_name is 'Наименование типа содержимого сообщения';
comment on column tbl_message_type.message_type_descr is 'Описание типа содержимого сообщения';

insert into tbl_message_type ( message_type_name, message_type_descr ) values 
( 'text','обычный текст без форматирования' ),
( 'markdown','текст с markdown-форматированием' ),
( 'html','текст с html-форматированием' )
;

create table tbl_api_keys(
  api_key_id serial,
	api_key varchar(128) not null,
	client_descr varchar(255) not null,
	primary key( api_key_id, api_key )
);

comment on table tbl_api_keys is 'Таблица со списком ключей доступа к АПИ бота';
comment on column tbl_api_keys.api_key_id is 'Идентификатор АПИ ключа';
comment on column tbl_api_keys.api_key is 'ХЭШ-АПИ ключ';
comment on column tbl_api_keys.client_descr is 'Имя клиент-сервиса, кому отдан ключ';

create table tbl_sending_queue (
id serial,
address_im varchar(100) DEFAULT NULL,
address_email varchar(100) DEFAULT NULL,
message varchar(1000) DEFAULT NULL,
message_type_id integer DEFAULT 1,
time_create timestamp DEFAULT now(),
time_start_process timestamp DEFAULT NULL,
time_send timestamp DEFAULT NULL,
time_read timestamp DEFAULT NULL,
sending_status_id integer DEFAULT 1,
sending_retry_num integer DEFAULT 0,
sender_uniq_id varchar(40) DEFAULT NULL,
im_event_id varchar(128) DEFAULT NULL,
edit_previouse boolean  DEFAULT FALSE,
api_key_id integer DEFAULT NULL,
error_description_im varchar(250) DEFAULT NULL ,
error_description_email varchar(250) DEFAULT NULL,
callback_url varchar(255) DEFAULT NULL,
callback_status_id integer DEFAULT 1,
callback_retry_num integer DEFAULT 0,
PRIMARY KEY (id)
);

comment on table tbl_sending_queue is 'Таблица с очередью сообщений на отправку';
comment on column tbl_sending_queue.id is 'Идентификатор сообщения на отправку';
comment on column tbl_sending_queue.address_im is 'Адрес пользователя в IM';
comment on column tbl_sending_queue.address_email is 'Адрес электронной почты получателя';
comment on column tbl_sending_queue.message is 'Текст сообщения';
comment on column tbl_sending_queue.message_type_id is 'Идентификатор типа содержимого сообщения';
comment on column tbl_sending_queue.time_create is 'Время формирования сообщения';
comment on column tbl_sending_queue.time_start_process is 'Время начала обработки сообщения отправщиком';
comment on column tbl_sending_queue.time_send is 'Время отправки сообщения';
comment on column tbl_sending_queue.time_read is 'Время прочтения сообщения';
comment on column tbl_sending_queue.sending_status_id is 'Идентификатор статуса отправки';
comment on column tbl_sending_queue.sending_retry_num is 'Количество попыток отправки сообщения';
comment on column tbl_sending_queue.sender_uniq_id is 'Идентификатор, переданный от отправителя, для идентификации сообщения';
comment on column tbl_sending_queue.im_event_id is 'Идентификатор, присвоенный отправленному сообщению в IM-системе (внутренний идентификатор IM-системы)';
comment on column tbl_sending_queue.edit_previouse is 'Если True и если есть предыдущее сообщение с таким же sender_uniq_id - в IM его текст заменяется на этот';
comment on column tbl_sending_queue.api_key_id is 'Идентификатор API-ключа системы-отправщика (кому выдан API-key)';
comment on column tbl_sending_queue.error_description_im is 'Текстовое описание ошибки отправки по IM';
comment on column tbl_sending_queue.error_description_email is 'Текстовое описание ошибки отправки по почте';
comment on column tbl_sending_queue.callback_url is 'url, по которому сообщать об изменении статуса рассылки сообщения';
comment on column tbl_sending_queue.callback_status_id is 'Статус отправки информации о рассылке по callback';
comment on column tbl_sending_queue.callback_retry_num is 'Количество попыток отправок информации по callback';
comment on column tbl_sending_queue.im_event_id is 'Внутренний идентификатор сообщения в системе IM';
