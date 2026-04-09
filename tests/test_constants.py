from core.constants import (
    AES_KEY_HARDCODED,
    APID_TC_COMMAND,
    APID_TC_SECRET_DEBUG,
    APID_TM_BME280,
    APID_TM_HEARTBEAT,
    APID_TM_IDLE,
    APID_TM_LIS2DH,
    BAUDRATE,
    CCSDS_CRC_SIZE,
    CCSDS_HDR_SIZE,
    CCSDS_MAX_FRAME_SIZE,
    CCSDS_MAX_PAYLOAD,
    CCSDS_SEC_HDR_SIZE,
    CCSDS_SEQ_STANDALONE,
    CCSDS_SPACECRAFT_ID,
    CCSDS_TYPE_TC,
    CCSDS_TYPE_TM,
    CCSDS_VERSION,
    TC_OP_BACKDOOR,
    TC_OP_EXEC,
    TC_OP_NOP,
    TC_OP_PING,
    TC_OP_PRIVILEGED,
    USB_PID,
    USB_VID,
    XOR_KEY,
    CommandStatus,
    ConnectionMode,
    DeviceHealth,
    EndpointState,
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
