// ng_top.v - integration of the cartridge logic (everything except pins).
//
// Console-side signals are the abstract ones of docs/AES_PINOUT.md (levels and
// real timing are a PCB/constraint matter).  MCU side: a register bus with
// the map of firmware/ngsd_loader.h and an SDRAM word port for the loader.
`timescale 1ns/1ps
module ng_top #(parameter BOOT_HEX = "", parameter MVS = 0) (
    input  wire        clk, rst,
    input  wire        tick12,
    // sprites + fix (CHA connector)
    input  wire        pck1b, pck2b, ca4, load, h, s2h1,
    input  wire [23:0] pbus,
    output wire [3:0]  gad, gbd,
    output wire [31:0] cr,            // MVS only (parameter MVS = 1): CR0-CR31
    output wire        dota, dotb,
    output wire [7:0]  fixd,
    output wire        c_rdy0, c_rdy1, s_fvalid,    // fetch status (debug/latency)
    // 68k (PROG connector)
    input  wire [22:0] p_a,
    input  wire        p_rd, p_wr,
    input  wire [15:0] p_wdata,
    output wire [15:0] p_rdata,
    output wire        p_rvalid,
    // Z80
    input  wire        z_io_rd, z_mrd,
    input  wire [15:0] z_a,
    output wire [7:0]  z_data,
    output wire        z_valid,
    // ADPCM data (abstract: byte read from the V region)
    input  wire        v_rd,
    input  wire [31:0] v_offs,
    output wire [7:0]  v_data,
    output wire        v_valid,
    // YM2610 ADPCM-A bus (SDRMPX, SDROE, SDRAD0-7, SDRA8/9, SDRA20-23)
    input  wire        ar_mpx, ar_oe_n,
    input  wire [7:0]  ar_ad_in,
    input  wire [1:0]  ar_a89,
    input  wire [3:0]  ar_a2023,
    output wire [7:0]  ar_ad_out,
    output wire        ar_drive,
    output wire [15:0] ar_late,
    // YM2610 ADPCM-B bus (SDPMPX, SDPOE, SDPAD0-7, SDPA8-11)
    input  wire        ap_mpx, ap_oe_n,
    input  wire [7:0]  ap_ad_in,
    input  wire [3:0]  ap_a811,
    output wire [7:0]  ap_ad_out,
    output wire        ap_drive,
    output wire [15:0] ap_late,
    // MCU register bus
    input  wire        reg_wr,
    input  wire [7:0]  reg_addr,
    input  wire [31:0] reg_wdata,
    output wire        run,
    output wire        stub,
    // MCU SDRAM access
    input  wire        mcu_req, mcu_we,
    input  wire [31:0] mcu_addr, mcu_wdata,
    output wire        mcu_full,
    output wire        mcu_rvalid,
    output wire [31:0] mcu_rdata,
    // SDRAM chip
    output wire [1:0]  sd_cs_n,
    output wire        sd_ras_n, sd_cas_n, sd_we_n,
    output wire [1:0]  sd_ba,
    output wire [12:0] sd_a,
    output wire [1:0]  sd_dqm,
    output wire [15:0] sd_dq_o,
    output wire        sd_dq_oe,
    input  wire [15:0] sd_dq_i
);
    // ---- registers (map of firmware/ngsd_loader.h) --------------------------
    reg        run_r, stub_r;
    reg [31:0] mapper, mapper_arg;
    reg [31:0] size [1:6], addr [1:6];
    integer k;
    always @(posedge clk) begin
        if (rst) begin
            run_r <= 0; stub_r <= 0; mapper <= 0; mapper_arg <= 0;
            for (k = 1; k <= 6; k = k + 1) begin size[k] <= 0; addr[k] <= 0; end
        end else if (reg_wr) begin
            case (reg_addr)
                8'h00: begin run_r <= reg_wdata[0]; stub_r <= reg_wdata[1]; end
                8'h01: mapper <= reg_wdata;
                8'h02: mapper_arg <= reg_wdata;
                default: begin
                    if (reg_addr >= 8'h10 && reg_addr <= 8'h15) size[reg_addr - 8'h0F] <= reg_wdata;
                    if (reg_addr >= 8'h20 && reg_addr <= 8'h25) addr[reg_addr - 8'h1F] <= reg_wdata;
                end
            endcase
        end
    end
    assign run = run_r;
    assign stub = stub_r;
    wire swap_req;
    always @(posedge clk) if (swap_req) stub_r <= 1'b0;   // 68k: game is ready, switch

    // boot RAM (docs/BOOT.md): regs 0x30 = index, 0x31 = data
    wire [15:0] boot_rdata;
    ng_boot #(.BOOT_HEX(BOOT_HEX)) bootram(.clk(clk),
        .idx_wr(reg_wr && reg_addr == 8'h30), .data_wr(reg_wr && reg_addr == 8'h31),
        .wdata(reg_wdata[15:0]), .raddr(p_a[8:0]), .rdata(boot_rdata));

    // next power of two >= n, minus 1 (n >= 1)
    function [19:0] pow2m1(input [31:0] n);
        reg [31:0] v;
        begin
            v = (n == 0) ? 0 : n - 1;
            v = v | (v >> 1); v = v | (v >> 2); v = v | (v >> 4);
            v = v | (v >> 8); v = v | (v >> 16);
            pow2m1 = v[19:0];
        end
    endfunction
    wire [19:0] c_mask = pow2m1(size[2] >> 7);
    wire [11:0] s_mask = pow2m1(size[3] >> 5);

    // ---- SDRAM chain ---------------------------------------------------------
    wire [7:0]   cl_req;
    wire [255:0] cl_addr;
    wire [7:0]   cl_rvalid;
    wire [63:0]  cl_rdata;
    wire         rq_valid, rq_we, rq_ready, rs_valid;
    wire [31:0]  rq_addr, rq_wdata;
    wire [63:0]  rs_rdata;

    ng_arb arb(.clk(clk), .rst(rst), .c_req(cl_req), .c_addr(cl_addr),
               .mcu_we(mcu_we), .mcu_wdata(mcu_wdata), .mcu_full(mcu_full),
               .c_rvalid(cl_rvalid), .c_rdata(cl_rdata),
               .req_valid(rq_valid), .req_we(rq_we), .req_addr(rq_addr),
               .req_wdata(rq_wdata), .req_ready(rq_ready),
               .rsp_valid(rs_valid), .rsp_rdata(rs_rdata));
    ng_sdram sdr(.clk(clk), .rst(rst), .req_valid(rq_valid), .req_we(rq_we),
                 .req_addr(rq_addr), .req_wdata(rq_wdata), .req_ready(rq_ready),
                 .rsp_valid(rs_valid), .rsp_rdata(rs_rdata),
                 .sd_cs_n(sd_cs_n), .sd_ras_n(sd_ras_n), .sd_cas_n(sd_cas_n),
                 .sd_we_n(sd_we_n), .sd_ba(sd_ba), .sd_a(sd_a), .sd_dqm(sd_dqm),
                 .sd_dq_o(sd_dq_o), .sd_dq_oe(sd_dq_oe), .sd_dq_i(sd_dq_i));

    assign cl_req[0] = mcu_req;
    assign cl_addr[31:0] = mcu_addr;
    assign mcu_rvalid = cl_rvalid[0];
    reg mcu_a2;                                  // one MCU read in flight
    always @(posedge clk) if (mcu_req) mcu_a2 <= mcu_addr[2];
    assign mcu_rdata  = mcu_a2 ? cl_rdata[63:32] : cl_rdata[31:0];

    // ---- clients (index 1..5 = C, S, P, M, V) -------------------------------
    wire c_mreq, s_mreq, p_mreq, m_mreq, v_mreq;
    wire [31:0] c_ma, s_ma, p_ma, m_ma, v_ma;
    assign cl_req[1] = c_mreq; assign cl_addr[63:32]   = c_ma;
    assign cl_req[2] = s_mreq; assign cl_addr[95:64]   = s_ma;
    assign cl_req[3] = p_mreq; assign cl_addr[127:96]  = p_ma;
    assign cl_req[4] = m_mreq; assign cl_addr[159:128] = m_ma;
    assign cl_req[5] = v_mreq; assign cl_addr[191:160] = v_ma;
    wire ar_mreq, ap_mreq; wire [31:0] ar_ma, ap_ma;
    assign cl_req[6] = ar_mreq; assign cl_addr[223:192] = ar_ma;
    assign cl_req[7] = ap_mreq; assign cl_addr[255:224] = ap_ma;

    generate if (MVS == 0) begin : g_aes
        ng_cfetch cf(.clk(clk), .rst(rst | ~run_r), .tick12(tick12), .pck1b(pck1b),
            .pbus(pbus), .ca4(ca4), .load(load), .h(h), .tile_mask(c_mask),
            .c_base(addr[2]), .gad(gad), .gbd(gbd), .dota(dota), .dotb(dotb),
            .mem_req(c_mreq), .mem_addr(c_ma), .mem_valid(cl_rvalid[1]),
            .mem_rdata(cl_rdata), .rdy0(c_rdy0), .rdy1(c_rdy1));
        assign cr = 32'd0;
    end else begin : g_mvs
        ng_cfetch_mvs cfm(.clk(clk), .rst(rst | ~run_r), .pck1b(pck1b),
            .pbus(pbus), .ca4(ca4), .tile_mask(c_mask), .c_base(addr[2]),
            .cr(cr), .ready(c_rdy0), .mem_req(c_mreq), .mem_addr(c_ma),
            .mem_valid(cl_rvalid[1]), .mem_rdata(cl_rdata));
        assign c_rdy1 = c_rdy0;
        assign gad = 4'd0; assign gbd = 4'd0; assign dota = 1'b0; assign dotb = 1'b0;
    end endgenerate
    ng_sfetch sf(.clk(clk), .rst(rst | ~run_r), .pck2b(pck2b), .pbus(pbus),
        .s2h1(s2h1), .tile_mask(s_mask), .s_base(addr[3]), .fixd(fixd),
        .fvalid(s_fvalid), .mem_req(s_mreq), .mem_addr(s_ma),
        .mem_valid(cl_rvalid[2]), .mem_rdata(cl_rdata));
    ng_pbank pb(.clk(clk), .rst(rst | (~run_r & ~stub_r)), .stub_en(stub_r),
        .boot_rdata(boot_rdata), .swap_req(swap_req),
        .bank_mask(8'h03), .p_base(addr[1]),
        .a(p_a), .rd(p_rd), .wr(p_wr), .wdata(p_wdata), .rdata(p_rdata),
        .rvalid(p_rvalid), .in_cart(), .mem_req(p_mreq), .mem_addr(p_ma),
        .mem_valid(cl_rvalid[3]), .mem_rdata(cl_rdata));

    wire [18:0] zm_addr;
    ng_zmc zmc(.clk(clk), .rst(rst | ~run_r), .io_rd(z_io_rd), .za(z_a),
               .m_addr(zm_addr), .m_sel());
    ng_rdport mport(.clk(clk), .rst(rst), .rd(z_mrd), .offs({13'd0, zm_addr}),
        .base(addr[4]), .mem_req(m_mreq), .mem_addr(m_ma),
        .mem_valid(cl_rvalid[4]), .mem_rdata(cl_rdata), .data(z_data), .valid(z_valid));
    ng_rdport vport(.clk(clk), .rst(rst), .rd(v_rd), .offs(v_offs),
        .base(addr[5]), .mem_req(v_mreq), .mem_addr(v_ma),
        .mem_valid(cl_rvalid[5]), .mem_rdata(cl_rdata), .data(v_data), .valid(v_valid));

    // ---- ADPCM-A / ADPCM-B buses (docs/TIMING.md s.11), V region ---------------
    wire ar_rd, ap_rd; wire [31:0] ar_off, ap_off;
    wire [7:0] ar_rdat, ap_rdat; wire ar_rval, ap_rval;
    ng_adpcm #(.B(0)) adpa(.clk(clk), .rst(rst | ~run_r), .mpx(ar_mpx), .oe_n(ar_oe_n),
        .ad_in(ar_ad_in), .a_mid({2'b00, ar_a89}), .a_top(ar_a2023), .ad_out(ar_ad_out),
        .ad_drive(ar_drive), .rd(ar_rd), .offs(ar_off), .rdata(ar_rdat),
        .rvalid(ar_rval), .late(ar_late));
    ng_rdport aport(.clk(clk), .rst(rst), .rd(ar_rd), .offs(ar_off), .base(addr[5]),
        .mem_req(ar_mreq), .mem_addr(ar_ma), .mem_valid(cl_rvalid[6]),
        .mem_rdata(cl_rdata), .data(ar_rdat), .valid(ar_rval));
    ng_adpcm #(.B(1)) adpb(.clk(clk), .rst(rst | ~run_r), .mpx(ap_mpx), .oe_n(ap_oe_n),
        .ad_in(ap_ad_in), .a_mid(ap_a811), .a_top(4'd0), .ad_out(ap_ad_out),
        .ad_drive(ap_drive), .rd(ap_rd), .offs(ap_off), .rdata(ap_rdat),
        .rvalid(ap_rval), .late(ap_late));
    ng_rdport bport(.clk(clk), .rst(rst), .rd(ap_rd), .offs(ap_off), .base(size[6] != 0 ? addr[6] : addr[5]),   // ADPCM-B: own ROM (VB) if loaded
        .mem_req(ap_mreq), .mem_addr(ap_ma), .mem_valid(cl_rvalid[7]),
        .mem_rdata(cl_rdata), .data(ap_rdat), .valid(ap_rval));
endmodule
