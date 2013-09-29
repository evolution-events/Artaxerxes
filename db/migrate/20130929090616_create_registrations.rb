class CreateRegistrations < ActiveRecord::Migration
  def change
    create_table :registrations do |t|
      t.belongs_to :user, index: true
      t.belongs_to :event, index: true
      t.string :status

      t.timestamps
    end
  end
end
