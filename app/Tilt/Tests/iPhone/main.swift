// The iPhone side of Apple Home in one tap (issue #50): Apple's add request, built as the app builds it. HomeKit is not
// in the Mac's SDK, so this runs in the iPhone simulator (tools/app_tests.sh). It checks the request only: opening
// Apple's add screen needs a real iPhone and a person.
import Foundation
import HomeKit
import Matter

var failures = 0, passed = 0
func check(_ ok: Bool, _ what: String, file: String = #file, line: Int = #line) {
    if ok { passed += 1 } else { failures += 1; print("FAIL line \(line): \(what)") }
}

let specQR = "MT:-24J0AFN00KA0648G00", specCode = "34970112332"   // the Matter spec's example device
let r = HomeSetup.request(qr: specQR, code: specCode, name: "Tilt Hub")
check(r?.matterPayload?.setupPasscode == 20202021, "the code goes in the request as a Matter payload")
check(r != nil && r?.payload == nil, "never in HomeKit's own payload field (only for MFi makers: it fails for us)")
check(r?.suggestedAccessoryName == "Tilt Hub", "the name is suggested")
check(HomeSetup.request(qr: "MT:not-a-code", code: "", name: nil) == nil, "a broken code: no request (the app shows the code instead)")
check(HomeSetup.wasClosed(HMError(.operationCancelled)), "the person closing Apple's screen: nothing more is shown")
check(!HomeSetup.wasClosed(HMError(.insufficientPrivileges)), "any other error: the app shows the code, saying why")
check(!HomeSetup.wasClosed(URLError(.timedOut)), "an error that is not Apple Home's: the code is shown too")

print("iPhone: \(passed) passed, \(failures) failed")
exit(failures == 0 ? 0 : 1)
