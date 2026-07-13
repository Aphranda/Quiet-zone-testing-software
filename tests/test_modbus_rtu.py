import unittest

from quiet_zone_tester.hardware.transport.modbus_rtu import ModbusRtuConfig, ModbusRtuSession


class _FakeSerial:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.is_open = True
        self.written: list[bytes] = []
        self.input_resets = 0

    def reset_input_buffer(self) -> None:
        self.input_resets += 1

    def reset_output_buffer(self) -> None:
        pass

    def write(self, data: bytes) -> None:
        self.written.append(data)

    def flush(self) -> None:
        pass

    def read(self, size: int) -> bytes:
        if not self.chunks:
            return b""
        chunk = self.chunks.pop(0)
        if len(chunk) > size:
            self.chunks.insert(0, chunk[size:])
            return chunk[:size]
        return chunk


class ModbusRtuSessionTest(unittest.TestCase):
    def test_transact_reads_fragmented_read_registers_response_to_complete_frame(self) -> None:
        body = bytes([0x01, 0x03, 0x04, 0x00, 0x01, 0x00, 0x02])
        crc = ModbusRtuSession.crc16(body).to_bytes(2, byteorder="little")
        fake_serial = _FakeSerial([body[:2], body[2:3], body[3:6], body[6:] + crc])
        session = ModbusRtuSession(ModbusRtuConfig(port="COM1", timeout_s=0.01, retries=0))
        session._serial = fake_serial

        response = session.transact(bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x02]))

        self.assertEqual(response, body + crc)
        self.assertEqual(fake_serial.input_resets, 1)
        self.assertEqual(len(fake_serial.written), 1)


if __name__ == "__main__":
    unittest.main()
