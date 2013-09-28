class User < ActiveRecord::Base
  has_one :address, class_name: 'UserAddress'
  has_many :medical_details
  has_many :emergency_contacts
end
