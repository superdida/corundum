#!/usr/bin/env python
"""

Copyright (c) 2019 Alex Forencich

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""

from myhdl import *
import os

import dma_ram
import axis_ep

module = 'dma_client_axis_source'
testbench = 'test_%s_512_64' % module

srcs = []

srcs.append("../rtl/%s.v" % module)
srcs.append("%s.v" % testbench)

src = ' '.join(srcs)

build_cmd = "iverilog -o %s.vvp %s" % (testbench, src)

def bench():

    # Parameters
    SEG_COUNT = 4
    SEG_DATA_WIDTH = 128
    SEG_ADDR_WIDTH = 12
    SEG_BE_WIDTH = int(SEG_DATA_WIDTH/8)
    RAM_ADDR_WIDTH = SEG_ADDR_WIDTH+(SEG_COUNT-1).bit_length()+(SEG_BE_WIDTH-1).bit_length()
    AXIS_DATA_WIDTH = 64
    AXIS_KEEP_ENABLE = (AXIS_DATA_WIDTH>8)
    AXIS_KEEP_WIDTH = (AXIS_DATA_WIDTH/8)
    AXIS_LAST_ENABLE = 1
    AXIS_ID_ENABLE = 1
    AXIS_ID_WIDTH = 8
    AXIS_DEST_ENABLE = 0
    AXIS_DEST_WIDTH = 8
    AXIS_USER_ENABLE = 1
    AXIS_USER_WIDTH = 1
    LEN_WIDTH = 20
    TAG_WIDTH = 8

    # Inputs
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    current_test = Signal(intbv(0)[8:])

    s_axis_read_desc_ram_addr = Signal(intbv(0)[RAM_ADDR_WIDTH:])
    s_axis_read_desc_len = Signal(intbv(0)[LEN_WIDTH:])
    s_axis_read_desc_tag = Signal(intbv(0)[TAG_WIDTH:])
    s_axis_read_desc_id = Signal(intbv(0)[AXIS_ID_WIDTH:])
    s_axis_read_desc_dest = Signal(intbv(0)[AXIS_DEST_WIDTH:])
    s_axis_read_desc_user = Signal(intbv(0)[AXIS_USER_WIDTH:])
    s_axis_read_desc_valid = Signal(bool(0))
    m_axis_read_data_tready = Signal(bool(0))
    ram_rd_cmd_ready = Signal(intbv(0)[SEG_COUNT:])
    ram_rd_resp_data = Signal(intbv(0)[SEG_COUNT*SEG_DATA_WIDTH:])
    ram_rd_resp_valid = Signal(intbv(0)[SEG_COUNT:])
    enable = Signal(bool(0))

    # Outputs
    s_axis_read_desc_ready = Signal(bool(0))
    m_axis_read_desc_status_tag = Signal(intbv(0)[TAG_WIDTH:])
    m_axis_read_desc_status_valid = Signal(bool(0))
    m_axis_read_data_tdata = Signal(intbv(0)[AXIS_DATA_WIDTH:])
    m_axis_read_data_tkeep = Signal(intbv(0)[AXIS_KEEP_WIDTH:])
    m_axis_read_data_tvalid = Signal(bool(0))
    m_axis_read_data_tlast = Signal(bool(0))
    m_axis_read_data_tid = Signal(intbv(0)[AXIS_ID_WIDTH:])
    m_axis_read_data_tdest = Signal(intbv(0)[AXIS_DEST_WIDTH:])
    m_axis_read_data_tuser = Signal(intbv(0)[AXIS_USER_WIDTH:])
    ram_rd_cmd_addr = Signal(intbv(0)[SEG_COUNT*SEG_ADDR_WIDTH:])
    ram_rd_cmd_valid = Signal(intbv(0)[SEG_COUNT:])
    ram_rd_resp_ready = Signal(intbv(0)[SEG_COUNT:])

    # PCIe DMA RAM
    dma_ram_inst = dma_ram.PSDPRam(2**16)
    dma_ram_pause = Signal(bool(0))

    dma_ram_port0 = dma_ram_inst.create_read_ports(
        clk,
        ram_rd_cmd_addr=ram_rd_cmd_addr,
        ram_rd_cmd_valid=ram_rd_cmd_valid,
        ram_rd_cmd_ready=ram_rd_cmd_ready,
        ram_rd_resp_data=ram_rd_resp_data,
        ram_rd_resp_valid=ram_rd_resp_valid,
        ram_rd_resp_ready=ram_rd_resp_ready,
        pause=dma_ram_pause,
        name='port0'
    )

    # sources and sinks
    read_desc_source = axis_ep.AXIStreamSource()
    read_desc_source_pause = Signal(bool(False))

    read_desc_source_logic = read_desc_source.create_logic(
        clk,
        rst,
        tdata=(s_axis_read_desc_ram_addr, s_axis_read_desc_len, s_axis_read_desc_tag, s_axis_read_desc_id, s_axis_read_desc_dest, s_axis_read_desc_user),
        tvalid=s_axis_read_desc_valid,
        tready=s_axis_read_desc_ready,
        pause=read_desc_source_pause,
        name='read_desc_source'
    )

    read_desc_status_sink = axis_ep.AXIStreamSink()

    read_desc_status_sink_logic = read_desc_status_sink.create_logic(
        clk,
        rst,
        tdata=(m_axis_read_desc_status_tag,),
        tvalid=m_axis_read_desc_status_valid,
        name='read_desc_status_sink'
    )

    read_data_sink = axis_ep.AXIStreamSink()
    read_data_sink_pause = Signal(bool(False))

    read_data_sink_logic = read_data_sink.create_logic(
        clk,
        rst,
        tdata=m_axis_read_data_tdata,
        tkeep=m_axis_read_data_tkeep,
        tvalid=m_axis_read_data_tvalid,
        tready=m_axis_read_data_tready,
        tlast=m_axis_read_data_tlast,
        tid=m_axis_read_data_tid,
        tdest=m_axis_read_data_tdest,
        tuser=m_axis_read_data_tuser,
        pause=read_data_sink_pause,
        name='read_data_sink'
    )

    # DUT
    if os.system(build_cmd):
        raise Exception("Error running build command")

    dut = Cosimulation(
        "vvp -m myhdl %s.vvp -lxt2" % testbench,
        clk=clk,
        rst=rst,
        current_test=current_test,
        s_axis_read_desc_ram_addr=s_axis_read_desc_ram_addr,
        s_axis_read_desc_len=s_axis_read_desc_len,
        s_axis_read_desc_tag=s_axis_read_desc_tag,
        s_axis_read_desc_id=s_axis_read_desc_id,
        s_axis_read_desc_dest=s_axis_read_desc_dest,
        s_axis_read_desc_user=s_axis_read_desc_user,
        s_axis_read_desc_valid=s_axis_read_desc_valid,
        s_axis_read_desc_ready=s_axis_read_desc_ready,
        m_axis_read_desc_status_tag=m_axis_read_desc_status_tag,
        m_axis_read_desc_status_valid=m_axis_read_desc_status_valid,
        m_axis_read_data_tdata=m_axis_read_data_tdata,
        m_axis_read_data_tkeep=m_axis_read_data_tkeep,
        m_axis_read_data_tvalid=m_axis_read_data_tvalid,
        m_axis_read_data_tready=m_axis_read_data_tready,
        m_axis_read_data_tlast=m_axis_read_data_tlast,
        m_axis_read_data_tid=m_axis_read_data_tid,
        m_axis_read_data_tdest=m_axis_read_data_tdest,
        m_axis_read_data_tuser=m_axis_read_data_tuser,
        ram_rd_cmd_addr=ram_rd_cmd_addr,
        ram_rd_cmd_valid=ram_rd_cmd_valid,
        ram_rd_cmd_ready=ram_rd_cmd_ready,
        ram_rd_resp_data=ram_rd_resp_data,
        ram_rd_resp_valid=ram_rd_resp_valid,
        ram_rd_resp_ready=ram_rd_resp_ready,
        enable=enable
    )

    @always(delay(4))
    def clkgen():
        clk.next = not clk

    def wait_normal():
        while read_desc_status_sink.empty() or read_data_sink.empty():
            yield clk.posedge

    def wait_pause_ram():
        while read_desc_status_sink.empty() or read_data_sink.empty():
            dma_ram_pause.next = True
            yield clk.posedge
            yield clk.posedge
            yield clk.posedge
            dma_ram_pause.next = False
            yield clk.posedge

    def wait_pause_sink():
        while read_desc_status_sink.empty() or read_data_sink.empty():
            read_data_sink_pause.next = True
            yield clk.posedge
            yield clk.posedge
            yield clk.posedge
            read_data_sink_pause.next = False
            yield clk.posedge

    @instance
    def check():
        yield delay(100)
        yield clk.posedge
        rst.next = 1
        yield clk.posedge
        rst.next = 0
        yield clk.posedge
        yield delay(100)
        yield clk.posedge

        # testbench stimulus

        cur_tag = 1

        enable.next = 1

        yield clk.posedge
        print("test 1: read")
        current_test.next = 1

        addr = 0x00000000
        test_data = b'\x11\x22\x33\x44'

        dma_ram_inst.write_mem(addr, test_data)

        data = dma_ram_inst.read_mem(addr, 32)
        for i in range(0, len(data), 16):
            print(" ".join(("{:02x}".format(c) for c in bytearray(data[i:i+16]))))

        read_desc_source.send([(addr, len(test_data), cur_tag, cur_tag, 0, 0)])

        yield read_desc_status_sink.wait(1000)
        yield read_data_sink.wait(1000)

        status = read_desc_status_sink.recv()
        read_data = read_data_sink.recv()

        print(status)
        print(read_data)

        assert status.data[0][0] == cur_tag
        assert read_data.data == test_data
        assert read_data.id[0] == cur_tag

        cur_tag = (cur_tag + 1) % 256

        yield delay(100)

        yield clk.posedge
        print("test 2: various reads")
        current_test.next = 2

        for length in list(range(1,66))+[128]:
            for offset in list(range(8,65,8))+list(range(4096-64,4096,8)):
                for wait in wait_normal, wait_pause_ram, wait_pause_sink:
                    print("length %d, offset %d"% (length, offset))
                    #addr = length * 0x100000000 + offset * 0x10000 + offset
                    addr = offset
                    test_data = bytearray([x%256 for x in range(length)])

                    dma_ram_inst.write_mem(addr & 0xffff80, b'\xaa'*(len(test_data)+256))
                    dma_ram_inst.write_mem(addr, test_data)

                    data = dma_ram_inst.read_mem(addr&0xfffff0, 64)
                    for i in range(0, len(data), 16):
                        print(" ".join(("{:02x}".format(c) for c in bytearray(data[i:i+16]))))

                    read_desc_source.send([(addr, len(test_data), cur_tag, cur_tag, 0, 0)])

                    yield wait()

                    status = read_desc_status_sink.recv()
                    read_data = read_data_sink.recv()

                    print(status)
                    print(read_data)

                    assert status.data[0][0] == cur_tag
                    assert read_data.data == test_data
                    assert read_data.id[0] == cur_tag

                    cur_tag = (cur_tag + 1) % 256

                    yield delay(100)

        raise StopSimulation

    return instances()

def test_bench():
    sim = Simulation(bench())
    sim.run()

if __name__ == '__main__':
    print("Running test...")
    test_bench()
