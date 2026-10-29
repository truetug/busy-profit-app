export type WeatherCode = number;

export type LocationSource = "request" | "geoip";

export type ApiLocation = {
  latitude: number;
  longitude: number;
  name: string | null;
  timezone: string;
  utc_offset_seconds: number;
  source: LocationSource;
};

export type ApiReading = {
  time: string;
  temperature: number;
  weather_code: WeatherCode;
  is_day: boolean;
};

export type ApiCurrent = ApiReading;

export type ApiHour = ApiReading;

export type ApiDayHalf = {
  temperature: number;
  weather_code: WeatherCode;
};

export type ApiDay = {
  date: string;
  day: ApiDayHalf;
  night: ApiDayHalf;
};

export type ForecastResponse = {
  location: ApiLocation;
  current: ApiCurrent;
  hourly: ApiHour[];
  daily: ApiDay[];
};

export type ApiErrorCode = 0 | 4001 | 4201 | 4202 | 4203 | 5000;

export type ErrorResponse = {
  error: {
    code?: ApiErrorCode | number;
    message: string;
    data?: Record<string, unknown>;
  };
};

export type ApiPlace = {
  name: string;
  country: string | null;
  country_code: string | null;
  admin1: string | null;
  latitude: number;
  longitude: number;
  timezone: string;
};

export type LocationsResponse = {
  results: ApiPlace[];
};
