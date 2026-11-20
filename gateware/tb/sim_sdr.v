// Behavioural SDR SDRAM (16 bit, 4 banks, CL3, BL2) with timing checks.
// Image: sdram.hex (32-bit words, little-endian halves).  Not synthesizable.
`timescale 1ns/1ps
module sim_sdr #(
    parameter MEMHW = 1 << 22,          // 16-bit words modelled (8 MiB)
    parameter TRCD = 3, TRC = 8, TRP = 3, TRFC = 8, REFI = 700, CL = 3
) (
    input  wire        clk,
    input  wire        cs_n, ras_n, cas_n, we_n,
    input  wire [1:0]  ba,
    input  wire [12:0] a,
    input  wire [1:0]  dqm,
    input  wire [15:0] dq_i,
    input  wire        dq_oe,
    output reg  [15:0] dq_o
);
    reg [15:0] mem [0:MEMHW-1];
    reg [31:0] img [0:MEMHW/2-1];
    integer errors = 0, nrd = 0, nwr = 0, nref = 0;
    integer now = 0;
    integer last_act [0:3]; integer pre_done [0:3];
    reg        active [0:3]; reg [12:0] row [0:3];
    integer last_ref; integer last_cmd;
    reg mode_ok = 0;
    integer i;
    integer rd_t0, rd_a;
    reg rd_pend = 0;
    initial begin
        for (i = 0; i < MEMHW; i = i + 1) mem[i] = 16'h0;
        $readmemh("sdram.hex", img);
        for (i = 0; i < MEMHW/2; i = i + 1) begin
            mem[2*i] = img[i][15:0]; mem[2*i+1] = img[i][31:16];
        end
        for (i = 0; i < 4; i = i + 1) begin
            last_act[i] = -1000; pre_done[i] = 0; active[i] = 0; row[i] = 0;
        end
        last_ref = 0; dq_o = 16'hzzzz;
    end

    task err(input [255:0] msg); begin
        errors = errors + 1; $display("SDRAM ERROR t=%0d: %0s", now, msg); end endtask

    reg [24:0] ra16;
    reg [1:0]  wr_phase = 0; reg [24:0] wr_a16; reg [1:0] wr_ba;
    reg [15:0] sd [0:7]; reg sv [0:7]; integer j;
    reg [2:0] wr_left = 0; reg [24:0] wr_cur; reg [1:0] wr_dqm_dummy;
    always @(posedge clk) begin
        now <= now + 1;
        // data pipeline for reads (burst of 2)
        for (j = 0; j < 7; j = j + 1) begin sd[j] <= sd[j+1]; sv[j] <= sv[j+1]; end
        sv[7] <= 0;
        // CL=3: the controller samples beat 0 on the 3rd edge after the command
        dq_o <= (sv[0] ? sd[0] : 16'hzzzz);
        // write second beat
        if (wr_left != 0) begin
            if (dq_oe) begin
                if (!dqm[0]) mem[wr_cur % MEMHW][7:0]  <= dq_i[7:0];
                if (!dqm[1]) mem[wr_cur % MEMHW][15:8] <= dq_i[15:8];
            end else err("write beat without data");
            wr_cur <= wr_cur + 1; wr_left <= wr_left - 1;
        end
        if (!cs_n && !(ras_n && cas_n && we_n)) begin
            // ---- command decode
            if (!ras_n && cas_n && we_n) begin                       // ACTIVE
                if (active[ba]) err("ACT to active bank");
                if (now - last_act[ba] < TRC) err("tRC violated");
                if (now < pre_done[ba]) err("tRP violated");
                active[ba] <= 1; row[ba] <= a; last_act[ba] <= now;
            end else if (ras_n && !cas_n) begin                      // READ/WRITE
                if (!active[ba]) err("R/W to idle bank");
                else if (now - last_act[ba] < TRCD) err("tRCD violated");
                ra16 = {row[ba], ba, a[9:0]};
                if (ra16 >= MEMHW) begin err("address outside modelled memory");
                end else if (we_n) begin                              // READ
                    nrd = nrd + 1;
                    for (j = 0; j < 4; j = j + 1) begin
                        sd[CL - 2 + j] <= mem[(ra16 + j) % MEMHW]; sv[CL - 2 + j] <= 1;
                    end
                end else begin                                        // WRITE
                    nwr = nwr + 1;
                    if (dq_oe) begin
                        if (!dqm[0]) mem[ra16][7:0]  <= dq_i[7:0];
                        if (!dqm[1]) mem[ra16][15:8] <= dq_i[15:8];
                    end else err("write beat 1 without data");
                    wr_left <= 3; wr_cur <= ra16 + 1;
                end
                if (a[10]) begin      // auto precharge
                    active[ba] <= 0; pre_done[ba] <= now + TRP + (we_n ? 1 : 3);
                end
            end else if (!ras_n && cas_n && !we_n) begin             // PRECHARGE
                if (a[10]) for (i = 0; i < 4; i = i + 1) active[i] <= 0;
                else active[ba] <= 0;
                for (i = 0; i < 4; i = i + 1) pre_done[i] <= now + TRP;
            end else if (!ras_n && !cas_n && we_n) begin             // REFRESH
                for (i = 0; i < 4; i = i + 1)
                    if (active[i]) err("REFRESH with active bank");
                if (now - last_ref < TRFC) err("tRFC violated");
                last_ref <= now; nref = nref + 1;
            end else if (!ras_n && !cas_n && !we_n) begin           // MODE
                mode_ok <= (a == 13'h032);
                if (a != 13'h032) err("unexpected mode register value");
            end
        end
        if (now - last_ref > 9 * REFI && mode_ok) begin
            err("refresh starvation"); last_ref <= now;
        end
    end
endmodule
