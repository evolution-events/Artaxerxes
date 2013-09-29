class Event < ActiveRecord::Base
  belongs_to :series
  has_many :registrations
  has_many :registered_users, through: :registrations

  def to_s
    name
  end
end
