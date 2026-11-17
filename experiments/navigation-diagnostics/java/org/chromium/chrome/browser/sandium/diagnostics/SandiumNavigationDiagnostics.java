package org.chromium.chrome.browser.sandium.diagnostics;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.zip.CRC32;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;

/** Opt-in, bounded, numeric-only diagnostic recording. No browsing content accepted. */
public final class SandiumNavigationDiagnostics {
    public enum Event {
        NAV_START(0, 5), NAV_REDIRECT(1, 2), NAV_FINISH(2, 5), FIRST_PAINT(3, 1),
        CAPTURE(4, 16), CONTROLS(5, 8), BACK_HANDOFF(6, 6), DARK_POLICY(7, 3),
        RENDERER_EXIT(8, 2), POPUP_REQUEST(9, 3), AD_ENGINE_LOAD(10, 6), AD_DECISION(11, 8),
        AD_WARNING_MARK(12, 0), USER_GESTURE(13, 2), CAPTURE_LAYER(14, 11), TIMEOUT(15, 0),
        MENU_READ(16, 5), MENU_SAVE(17, 6), MENU_RENDER(18, 5), REDIRECT_RESULT(19, 2), POPUP_RESULT(20, 6),
        BLUR_TRANSITION(21, 8), PREDICTIVE_BACK(22, 8), TRANSITION_LAYER(23, 16), AD_REQUEST_OMITTED(24, 1), DOCUMENT_PAINT(25, 3), TYPOGRAPHY_POLICY_DISPATCH(26, 3), LAYOUT_SHIFT_BATCH(27, 7);
        final int code;
        final int fields;
        Event(int code, int fields) { this.code = code; this.fields = fields; }
    }
    private static final String[] FIELD_NAMES = {
        "renderer_initiated,history,back,forward,user_gesture",
        "renderer_initiated,user_gesture", "committed,error_page,net_error,http_status,download",
        "signal_only", "sample,stage,native_window_x_px,native_window_y_px,web_window_x_px,web_window_y_px,native_w_px,native_h_px,web_w_px,web_h_px,overlap_px,passed_top_px,native_attached,web_attached,native_scroll_y_px,web_scroll_y_px",
        "reserved1,reserved2,reserved3,reserved4,reserved5,reserved6,reserved7,reserved8",
        "reserved1,reserved2,reserved3,reserved4,reserved5,reserved6", "policy,stage,outermost_main_frame",
        "termination_status,tab_destroyed", "request_token,user_gesture,disposition",
        "engine,load_source,last_result,completion_sequence,resource_generation,request_baseline",
        "request_token,phase,resource_type,blocked_by,flags_bits,redirect_present,rewrite_present,end_to_end_us",
        "", "type,outcome", "sample,kind,m00,m01,m02,m10,m11,m12,m20,m21,m22", "",
        "sequence,source,valid,count,order_fingerprint", "sequence,source,valid,count,order_fingerprint,outcome",
        "sequence,screen,visible_count,order_fingerprint,requested_page", "action,net_error",
        "request_token,status,reason,child_available,duration_us,reserved",
        "stage,state,detail,has_blur,has_fallback,blur_width_px,blur_height_px,delegate_top_px",
        "stage,state,navigation_state,detail,fallback,copied_native,width_px,height_px",
        "stage,depth,x_px,y_px,width_px,height_px,transform_identity,opacity,has_parent,top_px,viewport_width_px,viewport_height_px,dip_scale,kind,truncated,reserved",
        "count", "primary_document,browser_receipt,reserved", "packed_policy,outermost_main_frame,phase", "outermost_main_frame,count,total_score,non_input_score,input_or_scroll_count,first_renderer_ticks_us,last_renderer_ticks_us"
    };
    public static final String BUILD_REVISION = "__SANDIUM_DIAGNOSTIC_BUILD_REVISION__";
    private static final int MAX_EVENTS = 5000;
    private static final long MAX_NS = 120_000_000_000L;
    private static final ArrayList<Row> EVENTS = new ArrayList<>();
    private static final HashMap<Long, Long> NAV_IDS = new HashMap<>();
    private static boolean sRecording;
    private static long sStartNs;
    private static File sDirectory;
    private static File sJournal;
    private static long sWallStart;
    private static long sOffsetUs;
    private static long sNextNav;
    private static long sLastWall;
    private static int sSegment;
    private static int sRecoveredDiscarded;
    private static String sStorage = "not_initialized";
    private static final int MAGIC = 0x53444a32;
    private static final int JOURNAL_SCHEMA = 2;
    private static final long MAX_JOURNAL_BYTES = 2_000_000;
    public static String storageStatus() {
        synchronized (SandiumNavigationDiagnostics.class) { return sStorage; }
    }
    public static int recoveryDiscardedRecords() {
        synchronized (SandiumNavigationDiagnostics.class) { return sRecoveredDiscarded; }
    }
    public static void initialize(File directory) {
        synchronized (SandiumNavigationDiagnostics.class) {
            if (sDirectory != null) return;
            if (directory == null) { storageError(); return; }
            sDirectory = directory; sJournal = new File(directory, "events.bin");
            try {
                if ((!directory.isDirectory() && !directory.mkdirs()) || !directory.isDirectory()) throw new IOException();
                sStorage = "available";
                if (!sJournal.exists()) return;
                if (sJournal.length() > MAX_JOURNAL_BYTES) throw new IOException();
                EVENTS.clear(); NAV_IDS.clear(); sNextNav = 0;
                try (DataInputStream in = new DataInputStream(new FileInputStream(sJournal))) {
                    if (in.readInt() != MAGIC) throw new IOException();
                    sWallStart = in.readLong(); sEpoch = in.readLong() + 1;
                    if (in.readInt() != JOURNAL_SCHEMA || !BUILD_REVISION.equals(in.readUTF())) {
                        sRecording = false; sStorage = "incompatible_recording";
                        sEnd = "incompatible_recording"; return;
                    }
                    if (sWallStart <= 0 || sEpoch <= 0) throw new IOException();
                    sRecording = true; sEnd = "recording";
                    while (in.available() > 0) {
                        try {
                            int length = in.readInt();
                            if (length < 1 || length > 512) throw new IOException();
                            byte[] bytes = new byte[length]; in.readFully(bytes);
                            long expected = in.readLong(); CRC32 crc = new CRC32(); crc.update(bytes);
                            if (crc.getValue() != expected) throw new IOException();
                            readRecord(new DataInputStream(new ByteArrayInputStream(bytes)));
                        } catch (IOException | RuntimeException invalid) {
                            sRecoveredDiscarded++; sRecording = false; sEnd = "recovered_partial"; break;
                        }
                    }
                }
                long now = System.currentTimeMillis();
                sOffsetUs = Math.max(0, now - sWallStart) * 1000;
                // A modest wall-clock rollback across process death must not reverse event order.
                if (!EVENTS.isEmpty()) sOffsetUs = Math.max(sOffsetUs, EVENTS.get(EVENTS.size() - 1).micros);
                sLastWall = now; sStartNs = System.nanoTime(); sSegment++; NAV_IDS.clear();
                if (sRecording && (now < sWallStart || now - sWallStart >= 120000)) { sRecording = false; sEnd = "restart_time_limit_or_clock_change"; }
                if (EVENTS.size() >= MAX_EVENTS) { sRecording = false; sEnd = "event_limit"; persistState(); }
                if (sRecoveredDiscarded == 0) persistState();
                else sStorage = "recovered_valid_prefix";
            } catch (IOException | RuntimeException failure) { storageError(); }

        }
    }
    private static void storageError() { sStorage = "storage_error"; sRecording = false; sEnd = "storage_error"; }
    private static void readRecord(DataInputStream in) throws IOException {
        int kind = in.readUnsignedByte();
        if (kind == 1) {
            long micros = in.readLong();
            long nav = in.readLong();
            long ticks = in.readLong();
            int segment = in.readInt();
            int event = in.readInt();
            int count = in.readInt();
            if (event < 0 || event >= Event.values().length || count != Event.values()[event].fields || EVENTS.size() >= MAX_EVENTS || micros < 0 || micros > 120000000 || nav < 0 || nav > MAX_EVENTS || segment < 0 || ticks < -1) throw new IOException();
            double[] values = new double[count];
            for (int i = 0; i < count; i++) { values[i] = in.readDouble(); if (!Double.isFinite(values[i])) throw new IOException(); }
            if (in.available() != 0) throw new IOException();
            EVENTS.add(new Row(micros, nav, Event.values()[event], values, ticks, segment));
            sNextNav = Math.max(sNextNav, nav); sSegment = Math.max(sSegment, segment);
        } else if (kind == 2) {
            boolean recording = in.readBoolean(); String end = in.readUTF(); int dropped = in.readInt(); long omitted = in.readLong(); int segment = in.readInt();
            if (!end.matches("[a-z_]{1,48}") || dropped < 0 || omitted < 0 || segment < 0 || in.available() != 0) throw new IOException();
            sRecording = recording; sEnd = end; sDropped = dropped; sAdRequestOmitted = omitted; sSegment = segment;
        } else throw new IOException();
        if (in.available() != 0) throw new IOException();
    }
    private interface JournalWriter { void write(DataOutputStream out) throws IOException; }
    private static void append(JournalWriter writer) {
        if (sJournal == null || !sStorage.equals("available")) return;
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (DataOutputStream record = new DataOutputStream(bytes)) { writer.write(record); }
            byte[] payload = bytes.toByteArray(); CRC32 crc = new CRC32(); crc.update(payload);
            if (sJournal.length() + payload.length + 12 > MAX_JOURNAL_BYTES) throw new IOException();
            try (DataOutputStream out = new DataOutputStream(new FileOutputStream(sJournal, true))) { out.writeInt(payload.length); out.write(payload); out.writeLong(crc.getValue()); }
        } catch (IOException | RuntimeException failure) { storageError(); }
    }
    private static void persistState() {
        append(out -> { out.writeByte(2); out.writeBoolean(sRecording); out.writeUTF(sEnd); out.writeInt(sDropped); out.writeLong(sAdRequestOmitted); out.writeInt(sSegment); });
    }
    private static void persistRow(Row row) {
        append(out -> { out.writeByte(1); out.writeLong(row.micros); out.writeLong(row.nav); out.writeLong(row.sourceTicksUs); out.writeInt(row.segment); out.writeInt(row.event.code); out.writeInt(row.values.length); for (double value : row.values) out.writeDouble(value); });
    }
    private static boolean replaceJournal() {
        if (sJournal == null) return true;
        try {
            File temp = new File(sDirectory, "events.tmp");
            try (FileOutputStream file = new FileOutputStream(temp); DataOutputStream out = new DataOutputStream(file)) { out.writeInt(MAGIC); out.writeLong(sWallStart); out.writeLong(sEpoch); out.writeInt(JOURNAL_SCHEMA); out.writeUTF(BUILD_REVISION); out.flush(); file.getFD().sync(); }
            if (!temp.renameTo(sJournal)) throw new IOException();
            sStorage = "available"; return true;
        } catch (IOException | RuntimeException failure) { storageError(); return false; }
    }
    private static long sEpoch;
    private static int sDropped;
    private static long sAdRequestOmitted;
    private static String sEnd = "not_started";
    private static final class Row {
        final long micros;
        final long nav;
        final long sourceTicksUs;
        final int segment;
        final Event event;
        final double[] values;
        Row(long micros, long nav, Event event, double[] values, long sourceTicksUs, int segment) {
            this.micros = micros; this.nav = nav; this.event = event; this.values = values;
            this.sourceTicksUs = sourceTicksUs; this.segment = segment;
        }
    }
    private SandiumNavigationDiagnostics() {}
    public static boolean start() {
        synchronized (SandiumNavigationDiagnostics.class) {
            clear(); sStartNs = System.nanoTime(); sWallStart = System.currentTimeMillis(); sLastWall = sWallStart;
            sOffsetUs = 0; sNextNav = 0; sSegment = 0; sRecoveredDiscarded = 0;
            if (!replaceJournal()) return false;
            sRecording = true; sEnd = "recording"; persistState(); return sRecording;

        }
    }
    public static void stop() {
        synchronized (SandiumNavigationDiagnostics.class) {
            expire(); if (sRecording) { sRecording = false; sEnd = "user_stopped"; persistState(); }

        }
    }
    public static void clear() {
        synchronized (SandiumNavigationDiagnostics.class) {
            sRecording = false; sEpoch++; EVENTS.clear(); NAV_IDS.clear(); sDropped = 0; sAdRequestOmitted = 0; sEnd = "cleared"; sRecoveredDiscarded = 0;
            if (sJournal != null && sJournal.exists() && !sJournal.delete()) storageError();
            else if (sDirectory != null && sDirectory.isDirectory()) sStorage = "available";

        }
    }
    private static void expire() {
        long now = System.currentTimeMillis();
        if (sRecording && (now < sLastWall || now - sWallStart >= 120000 || sOffsetUs * 1000 + System.nanoTime() - sStartNs >= MAX_NS)) {
            sRecording = false; sEnd = "time_limit"; persistState();
        }
        sLastWall = now;
    }
    public static boolean isRecording() {
        synchronized (SandiumNavigationDiagnostics.class) { expire(); return sRecording; }
    }
    /** Every producer must supply the actual private-context flag, never a guessed false. */
    public static void record(Event event, long nativeNavigationId,
            boolean offTheRecord, double... values) {
        synchronized (SandiumNavigationDiagnostics.class) {
            recordInternal(event, nativeNavigationId, offTheRecord, values, -1);

        }
    }
    public static long sessionEpoch() {
        synchronized (SandiumNavigationDiagnostics.class) {
            expire(); return sRecording ? sEpoch : 0;

        }
    }
    public static void recordNativeForEpoch(long expectedEpoch, int eventCode,
            long navigationId, long sourceTicksUs, boolean offTheRecord, double[] values) {
        synchronized (SandiumNavigationDiagnostics.class) {
            if (expectedEpoch == 0 || expectedEpoch != sessionEpoch()) return;
            recordNative(eventCode, navigationId, sourceTicksUs, offTheRecord, values);

        }
    }
    public static void recordNative(int eventCode, long navigationId,
            long sourceTicksUs, boolean offTheRecord, double[] values) {
        synchronized (SandiumNavigationDiagnostics.class) {
            if (eventCode < 0 || eventCode >= Event.values().length || sourceTicksUs < 0) return;
            recordInternal(Event.values()[eventCode], navigationId, offTheRecord, values, sourceTicksUs);

        }
    }
    private static void recordInternal(Event event, long nativeNavigationId,
            boolean offTheRecord, double[] values, long sourceTicksUs) {
        expire();
        if (!sRecording || offTheRecord) return;
        if (event == null || values == null || values.length != event.fields) { sDropped++; persistState(); return; }
        for (double value : values) if (!Double.isFinite(value)) { sDropped++; persistState(); return; }
        if (event == Event.AD_REQUEST_OMITTED) {
            if (values[0] == 1) sAdRequestOmitted++; else sDropped++;
            persistState(); return;
        }
        if (EVENTS.size() >= MAX_EVENTS) { sRecording = false; sEnd = "event_limit"; persistState(); return; }
        long nav = 0;
        if (nativeNavigationId > 0) {
            Long existing = NAV_IDS.get(nativeNavigationId);
            if (existing == null) { existing = ++sNextNav; NAV_IDS.put(nativeNavigationId, existing); }
            nav = existing;
        }
        Row row = new Row(sOffsetUs + (System.nanoTime() - sStartNs) / 1000, nav, event,
                Arrays.copyOf(values, values.length), sourceTicksUs, sSegment);
        EVENTS.add(row); persistRow(row);
        if (EVENTS.size() == MAX_EVENTS) { sRecording = false; sEnd = "event_limit"; persistState(); }
    }
    /** Explicit user report only; not an automatic ad-warning detector. */
    public static void markAdWarning() {
        synchronized (SandiumNavigationDiagnostics.class) {
            record(Event.AD_WARNING_MARK, 0, false);

        }
    }
    public static String snapshotSummary() {
        synchronized (SandiumNavigationDiagnostics.class) {
            expire(); return EVENTS.size() + " events; " + sEnd + "; " + sDropped + " invalid events rejected; " + sStorage + "; recovered discarded tails: " + sRecoveredDiscarded;

        }
    }
    public static String snapshotJson() {
        synchronized (SandiumNavigationDiagnostics.class) {
            expire();
            StringBuilder out = new StringBuilder(1024);
            out.append("{\"build_revision\":\"").append(BUILD_REVISION).append("\",\"coverage_complete\":false,\"unconnected\":[\"renderer_dark_applied_ack\",\"renderer_typography_applied_ack\",\"gpu_presented_frame\",\"renderer_denied_popup\",\"ad_resource_scriptlet_readiness\",\"request_to_document_link\",\"popup_to_child_navigation_link\"],\"schema\":1,\"clock\":\"segmented_receive_us\",\"end\":\"")
                    .append(sEnd).append("\",\"invalid_events\":").append(sDropped)
                    .append(",\"storage\":\"").append(sStorage).append("\",\"recovered_discarded_tails\":").append(sRecoveredDiscarded)
                    .append(",\"restart_clock\":\"wall_elapsed_conservative_segmented_monotonic\",\"ad_requests_omitted\":").append(sAdRequestOmitted)
                    .append(",\"limits\":{\"events\":5000,\"seconds\":120},\"field_names\":{");
            Event[] kinds = Event.values();
            for (int i = 0; i < kinds.length; i++) {
                if (i != 0) out.append(',');
                out.append('"').append(kinds[i].name()).append("\":\"").append(FIELD_NAMES[i]).append('"');
            }
            out.append("},\"events\":[");
            for (int i = 0; i < EVENTS.size(); i++) {
                if (i != 0) out.append(',');
                Row row = EVENTS.get(i);
                out.append("{\"t_us\":").append(row.micros).append(",\"nav\":").append(row.nav)
                        .append(",\"process_segment\":").append(row.segment)
                        .append(",\"source_browser_ticks_us\":").append(row.sourceTicksUs)
                        .append(",\"event\":\"").append(row.event.name()).append("\",\"values\":[");
                for (int j = 0; j < row.values.length; j++) {
                    if (j != 0) out.append(','); out.append(row.values[j]);
                }
                out.append("]}");
            }
            return out.append("]}").toString();

        }
    }
}
