import { registerWebModule, NativeModule } from 'expo';

// XmuCookieModule is not available on the web platform.
class XmuCookieModule extends NativeModule<{}> {}

export default registerWebModule(XmuCookieModule, 'XmuCookieModule');
