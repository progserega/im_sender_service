insert into tbl_api_keys (api_key, client_descr) VALUES ('XXXXXXXXXXXXXXXXX', 'test api-key for develop');

CREATE view view_sending_queue_with_named_statuses AS 
select 
  a.id,
  a.address_im,
  a.address_email,
  a.message,
  d.message_type_name,
  a.time_create,
  a.time_start_process,
  a.time_send,
  a.time_read,
  b.sending_status_name as sending_status,
  a.sending_retry_num,
  a.sender_uniq_id,
  a.im_event_id,
  e.client_descr,
  a.error_description_im,
  a.error_description_email,
  a.callback_url,
  c.callback_status_name as callback_status,
  a.callback_retry_num,
  a.edit_previouse
  from tbl_sending_queue as a 
  LEFT JOIN tbl_sending_status as b ON a.sending_status_id = b.sending_status_id 
  LEFT JOIN tbl_callback_status as c ON a.callback_status_id = c.callback_status_id
  LEFT JOIN tbl_message_type as d ON a.message_type_id = d.message_type_id
  LEFT JOIN tbl_api_keys as e ON a.api_key_id = e.api_key_id
  order by id;
