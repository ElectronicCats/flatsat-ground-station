from core.constants import (
    USB_VID, USB_PID, BAUDRATE,
    ENDPOINT_RADIO0, ENDPOINT_RADIO1, ENDPOINT_SHELL,
    CCSDS_VERSION, CCSDS_TYPE_TM, CCSDS_TYPE_TC,
    CCSDS_SPACECRAFT_ID, CCSDS_MAX_PAYLOAD, CCSDS_HDR_SIZE,
    CCSDS_SEC_HDR_SIZE, CCSDS_CRC_SIZE, CCSDS_MAX_FRAME_SIZE,
    CCSDS_SEQ_STANDALONE,
    APID_TM_HEARTBEAT, APID_TM_BME280, APID_TM_LIS2DH,
    APID_TM_POWER, APID_TM_GPS, APID_TM_ALL_SENSORS, APID_TM_IDLE,
    APID_TC_COMMAND, APID_TC_SET_FREQ, APID_TC_SET_POWER,
    APID_TC_FW_UPDATE, APID_TC_SET_DIFFICULTY,
    APID_TC_DIAG_LOG, APID_TC_DIAG_MEM,
    APID_TC_CTF_FLAG, APID_TC_SECRET_DEBUG,
    TC_OP_NOP, TC_OP_PING, TC_OP_READ_SENSOR,
    TC_OP_SET_TM_RATE, TC_OP_OVERRIDE_SENSOR,
    TC_OP_READ_FLAG, TC_OP_PRIVILEGED, TC_OP_EXEC,
    TC_OP_CRYPTO_ORACLE, TC_OP_BACKDOOR,
    DeviceHealth, EndpointState, CommandStatus,
    ConnectionMode,
    AES_KEY_HARDCODED, XOR_KEY,
)


def test_usb_identifiers():
    assert USB_VID == 0x1209
    assert USB_PID == 0xBABC
    assert BAUDRATE == 115200


def test_ccsds_constants():
    assert CCSDS_VERSION == 0
    assert CCSDS_TYPE_TM == 0
    assert CCSDS_TYPE_TC == 1
    assert CCSDS_SPACECRAFT_ID == 0x02
    assert CCSDS_HDR_SIZE == 6
    assert CCSDS_SEC_HDR_SIZE == 4
    assert CCSDS_CRC_SIZE == 2
    assert CCSDS_MAX_FRAME_SIZE == 237
    assert CCSDS_MAX_PAYLOAD == 225
    assert CCSDS_SEQ_STANDALONE == 3


def test_apid_tm_values():
    assert APID_TM_HEARTBEAT == 0x001
    assert APID_TM_BME280 == 0x010
    assert APID_TM_LIS2DH == 0x011
    assert APID_TM_IDLE == 0x7FF


def test_apid_tc_values():
    assert APID_TC_COMMAND == 0x020
    assert APID_TC_SECRET_DEBUG == 0x539


def test_tc_opcodes():
    assert TC_OP_NOP == 0x00
    assert TC_OP_PING == 0x10
    assert TC_OP_PRIVILEGED == 0xD0
    assert TC_OP_EXEC == 0xEE
    assert TC_OP_BACKDOOR == 0xFF


def test_aes_key():
    assert len(AES_KEY_HARDCODED) == 16
    assert AES_KEY_HARDCODED == b"PWNSAT_K3Y_2026!"


def test_xor_key():
    assert XOR_KEY == b"PWNSAT"


def test_enums_exist():
    assert DeviceHealth.HEALTHY
    assert EndpointState.DISCONNECTED
    assert CommandStatus.PASS
    assert ConnectionMode.HARDWARE
    assert ConnectionMode.SIMULATED
