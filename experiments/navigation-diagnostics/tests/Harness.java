import org.chromium.chrome.browser.sandium.diagnostics.SandiumNavigationDiagnostics;
import org.chromium.chrome.browser.sandium.diagnostics.SandiumNavigationDiagnostics.Event;
public class Harness {
    static void check(boolean condition) {if(!condition) throw new AssertionError();}
    public static void main(String[] ignored) throws Exception {
        SandiumNavigationDiagnostics.clear();
        SandiumNavigationDiagnostics.record(Event.AD_WARNING_MARK, 0, false);
        check(SandiumNavigationDiagnostics.snapshotSummary().startsWith("0 events"));
        check(SandiumNavigationDiagnostics.start());
        SandiumNavigationDiagnostics.record(Event.NAV_START, 987654, true, 0,0,0,0,0);
        check(SandiumNavigationDiagnostics.snapshotSummary().startsWith("0 events"));
        double[] values={1,2,3,4,5};
        SandiumNavigationDiagnostics.record(Event.NAV_START, 987654, false, values);values[0]=999;
        SandiumNavigationDiagnostics.record(Event.NAV_REDIRECT, 987654, false, 1,0);
        SandiumNavigationDiagnostics.record(Event.NAV_FINISH, 123456, false, 1,0,0,200,0);
        SandiumNavigationDiagnostics.record(Event.CONTROLS, 0, false, Double.NaN);
        String json=SandiumNavigationDiagnostics.snapshotJson();
        check(!json.contains("987654")&&!json.contains("123456")&&!json.contains("999"));
        check(json.contains("\"nav\":1")&&json.contains("\"nav\":2"));
        check(json.contains("\"invalid_events\":1"));
        SandiumNavigationDiagnostics.stop();SandiumNavigationDiagnostics.markAdWarning();
        check(SandiumNavigationDiagnostics.snapshotSummary().startsWith("3 events"));
        SandiumNavigationDiagnostics.start();
        for(int i=0;i<5100;i++)SandiumNavigationDiagnostics.markAdWarning();
        check(!SandiumNavigationDiagnostics.isRecording());
        check(SandiumNavigationDiagnostics.snapshotSummary().startsWith("5000 events; event_limit"));
        SandiumNavigationDiagnostics.start();
        var field=SandiumNavigationDiagnostics.class.getDeclaredField("sStartNs");field.setAccessible(true);field.setLong(null,System.nanoTime()-121_000_000_000L);
        SandiumNavigationDiagnostics.markAdWarning();
        check(SandiumNavigationDiagnostics.snapshotSummary().startsWith("0 events; time_limit"));
        long oldEpoch=SandiumNavigationDiagnostics.sessionEpoch();
        SandiumNavigationDiagnostics.start();long epoch=SandiumNavigationDiagnostics.sessionEpoch();
        check(epoch!=oldEpoch);
        SandiumNavigationDiagnostics.recordNativeForEpoch(oldEpoch,12,0,42,false,new double[0]);
        check(SandiumNavigationDiagnostics.snapshotSummary().startsWith("0 events"));
        SandiumNavigationDiagnostics.recordNativeForEpoch(epoch,12,0,42,false,new double[0]);
        check(SandiumNavigationDiagnostics.snapshotSummary().startsWith("1 events"));
        check(SandiumNavigationDiagnostics.snapshotJson().contains("\"source_browser_ticks_us\":42"));
        SandiumNavigationDiagnostics.recordForEpoch(oldEpoch, SandiumNavigationDiagnostics.Event.NATIVE_REVEAL_VIEW, false, new double[16]);
        SandiumNavigationDiagnostics.recordForEpoch(epoch, SandiumNavigationDiagnostics.Event.NATIVE_REVEAL_VIEW, true, new double[16]);
        check(SandiumNavigationDiagnostics.snapshotSummary().startsWith("1 events"));
        SandiumNavigationDiagnostics.recordForEpoch(epoch, SandiumNavigationDiagnostics.Event.NATIVE_REVEAL_VIEW, false, new double[16]);
        check(SandiumNavigationDiagnostics.snapshotSummary().startsWith("2 events"));
        check(SandiumNavigationDiagnostics.snapshotJson().contains("\"source_browser_ticks_us\":-1"));
        SandiumNavigationDiagnostics.clear();
        check(SandiumNavigationDiagnostics.snapshotJson().contains("\"events\":[]"));
        System.out.println("RECORDER_HOST_TESTS_PASS");
    }
}
