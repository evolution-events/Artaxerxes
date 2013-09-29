class User < ActiveRecord::Base
  has_one :address, class_name: 'UserAddress'
  has_many :medical_details
  has_many :emergency_contacts
  has_many :registrations
  has_many :registered_events, through: :registrations

  def name
    if preposition.present? then
      "#{first_name} #{preposition} #{last_name}"
    else
      "#{first_name} #{last_name}"
    end
  end

  def to_s
    name
  end
end
