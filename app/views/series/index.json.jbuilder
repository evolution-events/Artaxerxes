json.array!(@series) do |series|
  json.extract! series, :name, :url
  json.url series_url(series, format: :json)
end
