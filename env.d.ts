/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** BUSY Bar address for dev mode (see .env). */
  readonly VITE_BUSY_ADDR?: string
  /** Base URL of the weather backend; set in CI (see .env). */
  readonly VITE_WEATHER_API?: string
}

/** `dispatcher` is not in lib.dom. `useDeviceKey` authorizes the request with the device key. */
interface BusyRequestInit extends RequestInit {
  dispatcher?: {
    connect?: {
      useDeviceKey?: boolean
    }
  }
}

declare function fetch(
  input: RequestInfo | URL,
  init?: BusyRequestInit,
): Promise<Response>

interface ImportMeta {
  readonly env: ImportMetaEnv
}

/** A .anim file is a binary device asset; Vite returns its URL. */
declare module '*.anim' {
  const src: string
  export default src
}

/** A device input event. */
type BusyInputEvent =
  | {
      readonly key: 'encoder'
      readonly action: 'clockwise' | 'counterclockwise'
      readonly delta: 1 | -1
    }
  | {
      readonly key: 'ok' | 'start' | 'back'
      readonly action: 'press' | 'release'
    }

/** Detaches the handler. The runtime may stop the app once nothing else keeps it alive. */
type BusyUnbind = () => void

/**
 * Subscribes to device input. Throws a TypeError on an unknown type, or when a handler is already attached.
 * @param type - Only 'input' is accepted.
 */
declare function listen(
  type: 'input',
  handler: (event: BusyInputEvent) => void,
): BusyUnbind

