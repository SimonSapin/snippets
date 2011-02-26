"""

    Read packets in a specific format instead of blocks or lines.
    
    Author: Simon Sapin
    License: BSD

"""
import logging


class PacketReader(object):
    """
    A packet is made of:
     * A 2-bytes delimiter
     * One byte: packet length as an unsigned char
     * A variable-size payload
    
    The length include its own byte, but not the delimiter: The length for
    3 bytes of payload is 4.
    
    This reader registers itself to the `loop` EventLoop to read from
    `serial_port`. `callback` is called with the payload of each read packet.
    Non-packets data (between the end of a packet according to its length and
    the next delimiter) is dropped.
    
    The blocking code for reading these packets is much simpler, but with this
    reader we can react to other events in the same EventLoop.
    """
    
    PACKET_DELIMITER = '\xf5\x5f'
    
    def __init__(self, loop, serial_port, callback, max_block_size=1024):
        self.port = serial_port
        self.callback = callback
        self.in_packet = False
        loop.push_back_reader(serial_port, max_block_size)(self.new_block)
    
    def new_block(self, data, push_back):
        assert data, 'End-of-file reached on the serial port. Should not happen'
        while 1:
            if not self.in_packet:
                result = self.find_packet_delimiter(data)
                if result is None:
                    # No delimiter yet.
                    dropped = len(data)
                    # The following half-delimiter thing only works if len==2
                    assert len(self.PACKET_DELIMITER) == 2
                    if data[-1] == self.PACKET_DELIMITER[0]:
                        # Could be the first half of a delimiter
                        push_back(self.PACKET_DELIMITER[0])
                        dropped -= 1
                    logging.info('Dropped %i non-packet bytes', dropped)
                    # Wait for more data
                    return
                # Packet starts here
                data = result
                self.in_packet = True
                if not data:
                    return
            result = self.read_packet(data)
            if result is None:
                # Not enough data yet. Push-back everything.
                push_back(data)
                return
            else:
                # Finished this packet.
                self.in_packet = False
                data = result # remaining data
                if data:
                    # We still have some data after this packet.
                    # Loop and start parsing the next packet.
                    continue
                else:
                    return
        
    def find_packet_delimiter(self, data):
        assert data
        try:
            delimiter_position = data.index(self.PACKET_DELIMITER)
        except ValueError:
            # No delimiter here :(
            return None
        if delimiter_position > 0:
            logging.info('Dropped %i non-packet bytes', delimiter_position)
        packet_start = delimiter_position + len(self.PACKET_DELIMITER)
        # Packet content (including the length byte) starts here:
        return data[packet_start:]
    
    def read_packet(self, data):
        """
        `data` begins just after a packet delimiter
        """
        length = ord(data[0])
        # The length includes the length byte itself, so it's at least 1.
        assert length >= 1
        if len(data) < length:
            # Not enough data yet
            return None
        packet = data[1:length] # skip length byte
        self.callback(packet)
        remaining_data = data[length:]
        return remaining_data


