class User < ActiveRecord::Base
  has_one :address, class_name: 'UserAddress'
  has_many :medical_details
  has_many :emergency_contacts
  has_many :registrations
  has_many :registered_events, through: :registrations

  def to_s
    if preposition? then
      "#{first_name} #{preposition} #{last_name}"
    else
      "#{first_name} #{last_name}"
    end
  end
end
