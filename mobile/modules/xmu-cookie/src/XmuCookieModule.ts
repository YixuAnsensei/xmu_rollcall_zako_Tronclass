import { NativeModule, requireNativeModule } from 'expo';

declare class XmuCookieModule extends NativeModule<{}> {
  getCookieForUrlAsync(url: string): Promise<string | null>;
  clearCookiesAsync(): Promise<void>;
}

export default requireNativeModule<XmuCookieModule>('XmuCookie');
