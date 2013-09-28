json.array!(@users) do |user|
  json.extract! user, :first_name, :preposition, :last_name, :username, :birthdate, :phone_number, :email, :gender, :hide_last_name
  json.url user_url(user, format: :json)
end
