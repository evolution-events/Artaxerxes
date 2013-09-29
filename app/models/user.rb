class User < ActiveRecord::Base
  has_one :address, class_name: 'UserAddress'
  has_many :medical_details
  has_many :emergency_contacts
  has_many :registrations
  has_many :registered_events, through: :registrations
end
