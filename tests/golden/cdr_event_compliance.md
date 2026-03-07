# Compliance Report - SA (PDPL)

**Status**: PASSED
**Findings**: 0

## PII Inventory

| Table | PII Columns |
|-------|------------|
| voice_cdr | msisdn, calling_imsi, called_number, called_imsi, cell_id, imei |
| data_cdr | msisdn, source_ip, cell_id, imei, sgsn_address, ggsn_address |
| sms_cdr | msisdn, called_number, smsc_address |
| mms_cdr | msisdn, smsc_address |
| ussd_cdr | msisdn |
| 5g_nr_event | msisdn, cell_id, imei |
| volte_cdr | msisdn, called_number |
