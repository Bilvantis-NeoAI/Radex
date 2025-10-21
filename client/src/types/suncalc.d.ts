declare module 'suncalc' {
  export function getTimes(date: Date, lat: number, lon: number): any;
  export function getPosition(date: Date, lat: number, lon: number): any;
  // add more signatures if you need them
  const _default: {
    getTimes: typeof getTimes;
    getPosition: typeof getPosition;
  };
  export default _default;
}