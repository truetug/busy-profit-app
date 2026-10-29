import type {
  ApiPlace,
  ErrorResponse,
  ForecastResponse,
  LocationsResponse,
  WeatherCode,
} from "./apiTypes.ts";

const BASE = (import.meta.env.VITE_WEATHER_API ?? "").replace(/\/+$/, "");

const PREFIX = "/weather/v1";

const SIGNED: BusyRequestInit = {
  dispatcher: { connect: { useDeviceKey: true } },
};

export type City = {
  lat: number;
  lon: number;
};

export type CurrentWeather = {
  /** Temperature, °C. */
  temp: number;
  code: WeatherCode;
  daylight: boolean;
};

export type ForecastHour = {
  /** Local hour of the day, 0..23. */
  hour: number;
  temp: number;
  code: WeatherCode;
  daylight: boolean;
};

export type DayForecast = {
  date: string;
  day: number;
  night: number;
  dayCode: WeatherCode;
  nightCode: WeatherCode;
};

export type Place = {
  name: string;
  timezone: string;
  lat: number;
  lon: number;
};

export type Forecast = {
  place: Place;
  current: CurrentWeather;
  hours: ForecastHour[];
  days: DayForecast[];
};

export const GRAPH_HOURS = 24;

export const FORECAST_DAYS = 7;

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${PREFIX}${path}`, SIGNED);

  if (!res.ok) {
    const detail = await res
      .json()
      .then((body) => (body as ErrorResponse).error?.message)
      .catch(() => undefined);
    throw new Error(`weather api: HTTP ${res.status}${detail ? ` — ${detail}` : ""}`);
  }

  return (await res.json()) as T;
}

/** Without a city the backend resolves the place by geoip. */
export async function fetchForecast(city?: City): Promise<Forecast> {
  const query =
    city === undefined ? "" : `?latitude=${city.lat}&longitude=${city.lon}`;
  const data = await get<ForecastResponse>(`/forecast${query}`);

  if (!data.current || !data.location) {
    throw new Error("weather api: no current in response");
  }

  return {
    place: {
      name: data.location.name ?? "",
      timezone: data.location.timezone,
      lat: data.location.latitude,
      lon: data.location.longitude,
    },
    current: {
      temp: data.current.temperature,
      code: data.current.weather_code,
      daylight: data.current.is_day,
    },
    hours: (data.hourly ?? []).slice(0, GRAPH_HOURS).map((hour) => ({
      hour: Number(hour.time.slice(11, 13)),
      temp: hour.temperature,
      code: hour.weather_code,
      daylight: hour.is_day,
    })),
    days: (data.daily ?? []).slice(0, FORECAST_DAYS).map((day) => ({
      date: day.date,
      day: day.day.temperature,
      night: day.night.temperature,
      dayCode: day.day.weather_code,
      nightCode: day.night.weather_code,
    })),
  };
}

export type FoundPlace = Place & {
  country: string;
  countryCode: string;
  region: string;
};

function toFoundPlace(place: ApiPlace): FoundPlace {
  return {
    name: place.name,
    timezone: place.timezone,
    lat: place.latitude,
    lon: place.longitude,
    country: place.country ?? "",
    countryCode: place.country_code ?? "",
    region: place.admin1 ?? "",
  };
}

export const MIN_QUERY = 2;
const MAX_QUERY = 100;

export async function searchLocations(query: string): Promise<FoundPlace[]> {
  const trimmed = query.trim().slice(0, MAX_QUERY);
  if (trimmed.length < MIN_QUERY) return [];

  const data = await get<LocationsResponse>(
    `/locations?query=${encodeURIComponent(trimmed)}`,
  );
  return (data.results ?? []).map(toFoundPlace);
}
