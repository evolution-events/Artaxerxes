json.array!(@registrations) do |registration|
  json.extract! registration, :user_id, :event_id, :status
  json.url registration_url(registration, format: :json)
end
