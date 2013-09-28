json.array!(@events) do |event|
  json.extract! event, :name, :title, :start_date, :end_date, :location_name, :location_info, :description, :url, :series_id
  json.url event_url(event, format: :json)
end
